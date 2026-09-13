# Revisão arquitetural e de APIs

Revisão de código e documentação oficial consultada em 12/09/2026. Esta revisão não
substitui a verificação no Supervisor da instalação alvo.

## Decisões arquiteturais

Python com asyncio/aiohttp permite acompanhar requisições longas sem bloquear o
servidor web. A manutenção é uma máquina de estados de passos explícitos; reboot
tem estado separado e compartilha o mutex somente para decisões críticas.
SQLite foi escolhido para gravar lock, execução e marcadores de agenda de forma
atômica. Não se usa somente um arquivo PID como prova de uma execução pendente.

O processo principal executa reconciliação a cada 10 segundos. A espera de reboot
usa o prazo persistido e o intervalo configurado de 5 minutos. A agenda usa datas
do fuso do Home Assistant e impede duplicação durante a repetição de hora no DST.
O horário perdido é recuperado no mesmo dia; reboot não é enviado após seu prazo.

Uma intenção gravada sem resposta não é repetida, pois a API não fornece chaves
de idempotência para essas operações. Jobs conhecidos e versões podem resolver
a intenção; os casos sem prova mantêm o lock e exigem intervenção explícita.

## Permissões

O manifesto usa `hassio_api`, `homeassistant_api`, `hassio_role: manager`, `ingress`
e `panel_admin`. O papel manager permite os caminhos usados conforme o mapa
`ROLE_MANAGER` em [security.py do Supervisor](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/middleware/security.py).
Nenhum endpoint implementado exige o papel admin conforme esse mapa.

Não há full_access, docker_api, privileged, host_network, SYS_ADMIN, dispositivos
do host ou portas publicadas. O Dockerfile usa a inicialização padrão do Docker,
sem s6; por isso `init: true` é apropriado.

O servidor aceita apenas o peer Ingress `172.30.32.2`, sem confiar em X-Forwarded-For,
e exige token CSRF nos POSTs. A confirmação de reboot também é validada no backend.
Credenciais permanecem no ambiente do processo, fornecidas pelo Supervisor.

## Endpoints e confirmação

| Operação | Caminho | Validação |
| --- | --- | --- |
| Descoberta | GET /available_updates, /core/info, /os/info, /addons | Planos por categoria e versão |
| Backup | POST /backups/new/full | background, job e backup completo com nome único |
| App | POST /store/addons/{slug}/update | background, job e versão instalada |
| Core | POST /core/update | Requisição síncrona, versão e API operacional |
| OS | POST /os/update | Instalação pendente e versão ativa depois do reboot |
| Jobs | GET /jobs/info, /jobs/{id} | Recursão em child_jobs; erros e done |
| Reboot | POST /host/reboot | force=false, boot_timestamp e health |
| Supervisor nativo | GET /supervisor/info; POST /supervisor/options | auto_update=true |
| Opções próprias | POST /addons/self/options | Opções completas validadas |

Esses contratos foram conferidos nos [endpoints oficiais](https://developers.home-assistant.io/docs/api/supervisor/endpoints/).
Não se usa o caminho depreciado `/addons/{slug}/update` nem `/supervisor/update`.
Core e OS não recebem um parâmetro background inventado.

A separação atual entre instalação de OS e reboot foi conferida também no
[gerenciador de OS](https://github.com/home-assistant/supervisor/blob/main/supervisor/os/manager.py)
e na [API de OS](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/os.py).
O app recusa o contrato legado sem version_pending, em vez de assumir adiamento.

O token do Core usa o proxy do Supervisor. O registro de entidades é consultado pelo
[protocolo WebSocket](https://developers.home-assistant.io/docs/api/websocket/), e as
instalações utilizam a [integração update](https://www.home-assistant.io/integrations/update/).
Foi revisado também o [contrato de configuração de Apps](https://developers.home-assistant.io/docs/apps/configuration/)
para startup, Ingress e build direto pelo Dockerfile.

## Limites materiais

- O lock evita concorrência entre rotinas deste App; não pode reservar globalmente
  jobs de outros clientes no Supervisor. A verificação dupla reduz, mas não elimina,
  a janela entre consultar jobs e enviar o reboot.
- HACS e firmware variam entre integrações. Sem registro/capacidade comprovada,
  nenhuma instalação automática é feita.
- A fila não força, cancela ou executa rollback de operações externas. Timeouts
  deixam evidências persistidas e impedem operações conflitantes.
- Se o Supervisor remover um job antes da recuperação, não se presume sucesso do
  backup/App somente porque um POST foi enviado anteriormente.
- Falhas de disco/corrupção do banco interrompem o início do serviço; o estado não
  é silenciosamente recriado. Não houve simulação de falha física de armazenamento.
- A imagem Docker foi construída para amd64 e aarch64 no GitHub Actions, conforme
  PUBLICATION.md. A instalação Ingress e o comportamento físico em HA OS continuam
  pendentes de homologação; a máquina local desta entrega não disponibilizou Docker.
