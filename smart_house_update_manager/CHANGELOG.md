# Changelog

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
