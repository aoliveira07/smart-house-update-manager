# Changelog

## 0.1.2 — 2026-10-06

- Adicionada reconciliação automática para operações que expiraram sem confirmação.
- Jobs ainda ativos continuam protegidos; a versão instalada é aceita como evidência
  de sucesso mesmo depois do timeout.
- Jobs ausentes ou concluídos sem aplicar a versão entram em nova tentativa segura,
  com backoff e limite persistido de tentativas, liberando o lock quando esgotado.
- POSTs sem confirmação não são repetidos cegamente; permanecem em reconciliação
  limitada e só liberam o lock depois de provar que não há atividade crítica.
- Histórico e painel passam a registrar a fase `RECOVERY` e a tentativa de recuperação.
- Incluídos testes para recuperação após timeout, reinício do App e ausência de job.

## 0.1.1 — 2026-10-04

- Corrigido o bootstrap tardio da agenda: a primeira inicialização não repete manutenção ou reboot já perdidos.
- Falhas de preflight sem mutação incerta agora terminam como `deferred` e liberam o lock persistente.
- Operações incertas continuam em `blocked` e exigem reconciliação explícita antes de qualquer repetição.
- Adicionada validação pós-update que falha quando um item planejado permanece pendente na mesma versão alvo.
- Histórico e eventos registram origem, descoberta, seleção, operação e validação; o Ingress exibe resultado, motivo e pendências.
- Incluídos testes de regressão para bootstrap, timeout seguro e update ainda pendente.

## 0.1.0 — 2026-09-12

- Primeira entrega SH-005 para homologação.
- Manutenção e reboot diário independentes, estado SQLite e recuperação de jobs.
- Backup confirmado, Apps/HACS/Core/OS, classificação conservadora e auto-update nativo do Supervisor.
- Ingress administrativo, CSRF, histórico, configuração persistida e notificações.
- Dockerfile multiarch, workflows de testes e GHCR, testes automatizados e documentação.
- Nenhuma instalação real, publicação ou migração de automações realizada nesta entrega.
