# Primeira entrega — SH-005

Data: 12/09/2026. Versão: 0.1.0. Status: código preparado para homologação.

## Entregue

- Árvore completa e arquivos integrais, sem exigir montagem manual de trechos.
- Home Assistant App com opções, Dockerfile, run.sh, Python, painel, traduções,
  ícone, logo e documentação.
- Lock persistente, retomada por estado, backups e jobs, classificação,
  auto-update nativo do Supervisor, reboot diário e confirmação por boot_timestamp.
- Workflows de testes e build multiarch com publicação GHCR explícita.
- Revisão de permissões, endpoints atuais e tratamento de reboot em AUDIT.md.
- Matriz de cobertura dos 30 cenários originais e suite automatizada.

## Validação realizada

**60 testes aprovados**, executados localmente em Windows com Python 3.12.
Incluem simulações de API e testes HTTP/WebSocket em servidores locais de teste.
O resultado bruto está em TEST_RESULTS.txt, juntamente com validação de manifests,
sintaxe Python, configuração e limites de permissão.

O painel foi aberto no navegador local com dados simulados e inspecionado
visualmente. Status, agenda, backup, reboot, tabela e histórico foram renderizados.
A proteção de peer Ingress e CSRF foi verificada por testes automatizados;
a prévia local usou exclusivamente APIs falsas e não conecta a um Home Assistant.

## Validação ainda necessária

Não há Docker disponível nesta máquina, portanto o build da imagem não foi executado.
Os workflows estão preparados, mas não rodaram no GitHub. Não foi feita instalação
em HA OS nem validação física de backup, updates, reboot, Ingress ou permissões.
Não se declara SH-005 homologado.

O manifesto usa build local até que sejam informadas as coordenadas reais e publicada
a imagem GHCR. O script tools/prepare_registry.py regrava os manifests completos para
usar a imagem publicada. Não existe URL de repositório fictícia no pacote.

## Decisões que exigem atenção na homologação

1. O padrão pedido `dry_run: false` foi preservado. Ative Dry Run antes do primeiro início.
2. OS exige o contrato `version_pending`; Supervisores legados são recusados para evitar
   uma reinicialização imediata inesperada.
3. Respostas perdidas não provocam reenvio de POST. Uma operação incerta pode manter a
   execução bloqueada e impedir reboot até reconciliação ou confirmação do operador.
4. Jobs externos não compartilham o lock do App. Consulte a janela residual entre
   verificação e reboot explicada em AUDIT.md.
5. Firmware exige os dois controles habilitados. Allowlist/denylist permanecem futuras.

## Git inicial e publicação

A preparação Git local ocorre somente após testes e revisão: branch main e arquivos
no índice para revisão do commit inicial. Nenhum commit com autoria inventada,
remote, push, tag, publicação GHCR ou alteração de automações faz parte desta entrega.

Mensagem sugerida: `feat: initial SH-005 Smart House Update Manager`.
Após conferir a autoria Git e revisar os arquivos, o proprietário pode criar o commit
inicial e escolher o repositório de destino. As seis automações atuais foram preservadas.
