# Manual operacional — SH-005

## Instalação e primeira execução

Requer Home Assistant OS com Supervisor, acesso às APIs de Apps e Core e um sistema
amd64 ou aarch64. A instalação local usa o Dockerfile; a distribuição por imagens
usa GHCR após configurar as coordenadas reais do repositório.

Instale sem iniciar, mude `dry_run` para `true` nas opções do App e só então inicie.
O App inicia automaticamente nos boots seguintes (`boot: auto`, `startup: application`).
Abra “Update Manager” no painel lateral com uma conta administradora.

O modo global Dry Run também bloqueia o botão de reboot manual. “Executar Dry Run”
é uma execução individual sem backup, instalação, reboot ou alteração do auto-update
do Supervisor. A consulta de atualizações não modifica componentes.

## Configuração

As opções completas estão em `config.yaml`. O painel permite editar JSON validado e
grava a configuração em `/addons/self/options`. A aba de opções do Supervisor continua
sendo a fonte persistente: alterações feitas nela são lidas no próximo início do App.
Edições feitas pelo painel passam a valer imediatamente, se não houver execução pendente.

| Opção | Padrão | Efeito |
| --- | --- | --- |
| enabled | true | Habilita novas rotinas e reboot; Dry Run manual continua disponível |
| maintenance_time | 04:00 | Horário local da manutenção |
| timezone | auto | Usa `time_zone` do Core; aceita fuso IANA explícito |
| daily_host_reboot.enabled | true | Habilita o reboot diário independente |
| daily_host_reboot.time | 05:30 | Horário local do reboot |
| daily_host_reboot.retry_interval_minutes | 5 | Intervalo entre verificações de segurança |
| daily_host_reboot.max_wait_minutes | 120 | Prazo desde o horário planejado, inclusive após restart |
| daily_host_reboot.force | false | Deve permanecer false; true é rejeitado |
| updates.core / os / apps / hacs_software | true | Seleciona as categorias automáticas |
| updates.firmware | false | Exige também automatic_firmware_updates=true |
| automatic_firmware_updates | false | Segunda ativação explícita da política de firmware |
| updates.unknown | false | Deve permanecer false; true é rejeitado |
| backup.enabled | true | Cria um backup completo antes da fila |
| backup.only_when_updates | true | Deve permanecer true; reboot não cria backup |
| backup.timeout_minutes | 60 | Prazo persistido de conclusão do backup |
| supervisor.ensure_native_auto_update | true | Habilita a opção nativa quando necessário |
| notifications.success / failure / reboot_failure | true | Controla notificações persistentes no Core |
| dry_run | false | Simulação global quando true |
| update_timeout_minutes | 120 | Prazo de update e espera por jobs antes de operar |
| health_timeout_minutes | 15 | Prazo para confirmar reboot, APIs e versões |

Desabilitar backup é uma decisão explícita: o histórico registra `disabled`.
Não existe backup periódico independente. Allowlist e denylist de firmware são
extensões futuras; a versão inicial implementa somente a política global solicitada.

## Classificação

Supervisor, Core, OS e Apps são descobertos pelas APIs oficiais. As entidades da
integração `hassio` são excluídas da fila `update.install`, evitando duplicação.
O próprio App é excluído pelo slug real, incluindo o prefixo do repositório.

Para as demais entidades, `device_class=firmware` tem prioridade. A integração
`hacs` ou uma classe explícita `software`, com registro de origem disponível,
permite a classificação HACS_SOFTWARE. Sem evidência suficiente, usa-se UNKNOWN.
Uma falha ao consultar o registro aborta a descoberta; nomes parecidos com HACS
não são usados como prova. A entidade precisa expor a capacidade INSTALL.
Não há suporte universal a integrações sem entidade update ou sem ação install.

## Execução e retomada

SQLite em `/data/state.sqlite3` mantém execuções, opções utilizadas por cada execução,
lock lógico, jobs, prazos, versões, reboot e eventos. Usa transações, WAL e sincronização
FULL. Um lock Linux adicional impede dois processos de atuar sobre o mesmo banco.
Não apague o banco ou o lock para contornar uma falha.

Cada POST tem uma intenção persistida antes do envio. Backup e Apps exigem `job_id`;
`done=true` sem erros nos filhos e a validação do resultado são obrigatórios.
Core e OS usam chamadas síncronas oficiais em uma tarefa assíncrona, mantendo o painel
disponível. A versão alvo e o prazo ficam persistidos antes da chamada.

No restart, o App retoma o job conhecido ou verifica a versão alvo sem repetir o POST.
Se a resposta se perdeu sem evidência suficiente, a execução fica bloqueada. A rotina
diária de reboot continua planejada, mas não interrompe uma operação incerta.
O timeout não cancela uma operação que pode continuar no Supervisor.

Se uma operação falhou ou excedeu o prazo, a fila não continua automaticamente,
mesmo que a operação termine depois. A reconciliação pode liberar o lock com resultado
de falha. Se não for possível reconciliar, verifique o Supervisor e a integração de
origem; só após confirmar o término externo use “Encerrar execução bloqueada como falha”.
Esse botão exige confirmação e recusa encerrar enquanto houver jobs ou updates ativos.

## Reboot diário e OS

A agenda é registrada por data local, independentemente da existência de updates.
O restart do Core não satisfaz o reboot diário. Um reboot manual é separado da agenda
diária e pode resultar em dois reboots se for feito perto do horário programado.

Quando há jobs, atualizações de entidades ou manutenção ativa, o reboot é adiado
em 5 minutos. Jobs desconhecidos e filhos ativos de jobs concluídos também bloqueiam.
Se a API não responder, não se presume segurança. Ao exceder 120 minutos, a tentativa
do dia falha, gera uma notificação e não é reenviada automaticamente no mesmo dia.

O update do OS exige que `/os/info` exponha `version_pending`, sinalizando o contrato
atual em que instalação e reboot são separados. Supervisores antigos são recusados
antes de enviar `/os/update`. Uma versão no slot inativo não significa OS atualizado
com sucesso: o run aguarda o reboot e a validação da versão ativa.

Antes de reiniciar, grava-se `boot_timestamp`; somente um novo valor, APIs operacionais,
Core RUNNING, versões confirmadas e ausência de jobs ativos permitem registrar sucesso.
Resposta perdida no POST de reboot não leva a um segundo POST. A primeira entrega
usa `force=false` em todas as solicitações.

Se o reboot falhar, uma instalação de OS pendente mantém a execução aberta para a
próxima tentativa manual ou diária. Não há rollback automático. Uma versão errada
após reboot é registrada como falha. Uma indisponibilidade prolongada de APIs impede
confirmar sucesso, mesmo que o host tenha de fato reiniciado.

## Histórico, notificações e diagnóstico

O painel exibe as últimas 100 execuções, 100 resultados de reboot e 300 eventos.
As execuções e eventos permanecem no banco; não há remoção automática nesta versão.
As notificações são persistentes no Home Assistant e ficam em fila caso o Core esteja
indisponível. Logs usam run_id e fases controladas; tokens e respostas HTTP brutas não
são incluídos. Erros preexistentes dos logs do Core não participam do health check.

## Homologação e migração

1. Instalar com Dry Run global ativado e manter as automações atuais intactas.
2. Validar Ingress, horários, fuso, classificação e exclusão do próprio App.
3. Em janela controlada, testar backup real e verificar o job e o backup no Supervisor.
4. Testar uma atualização real selecionando apenas a categoria desejada nas opções.
5. Testar reboot manual e conferir os dois boot_timestamp e o health check.
6. Testar reboot diário sem update, depois com update do Core/App.
7. Testar update do OS e confirmar que houve apenas o reboot diário esperado.
8. Reiniciar o App durante um job de teste e validar a retomada sem duplicação.
9. Testar notificação de falha e revisar o histórico por alguns ciclos.
10. Somente após esses testes, o operador desabilita as seis automações antigas.
11. Observar mais alguns ciclos e então homologar SH-005.

Evite sobrepor o ensaio real aos horários das automações existentes; o App não tem
lock compartilhado com automações externas. Ele não as modifica nem as desativa.
O Supervisor não oferece uma transação pública que reserve todos os jobs entre a
consulta e o reboot; o App faz uma segunda verificação imediatamente antes do POST,
mas uma ação externa ainda pode começar nesse intervalo. `force=false` preserva a
proteção nativa de migração offline do Core; a homologação deve incluir concorrência externa.
