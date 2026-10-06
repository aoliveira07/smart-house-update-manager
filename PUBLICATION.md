# Publicação — Smart House Update Manager 0.1.3

## Release atual

- Tag: https://github.com/aoliveira07/smart-house-update-manager/tree/v0.1.3
- Commit: `d12d31e4d569663f8b252309b7605e5310c487b6`
- Imagem: `ghcr.io/aoliveira07/smart-house-update-manager:0.1.3`
- Workflow de testes: https://github.com/aoliveira07/smart-house-update-manager/actions/runs/37432970204
- Workflow de build/publicação: https://github.com/aoliveira07/smart-house-update-manager/actions/runs/37432970281
- 68 testes passaram localmente; os workflows de testes e build/publicação concluíram com sucesso.

Esta versão reconhece a atualização HACS baixada com reinício requerido, limita a
confirmação HTTP a 60 segundos e reconcilia evidência de versão antes de qualquer
nova tentativa, evitando duplicidade e destravando a fila de Core/OS.

## Histórico — 0.1.2

- Tag: https://github.com/aoliveira07/smart-house-update-manager/tree/v0.1.2
- Commit: `e8291715670c904fc3ed0a4e303c1c446b09c4d4`
- Imagem: `ghcr.io/aoliveira07/smart-house-update-manager:0.1.2`
- Digest do índice OCI: `sha256:ece1b16afb55b39e062b55ea894a4b0e977b6d2190fee62a2530c79c98622aa7`
- Manifestos publicados: `linux/amd64` (`sha256:544f8a1541aaee6b452c871b36b9b944e41b7da9a5186c529679c696e69164b3`) e `linux/arm64` (`sha256:f4178a6c6bf64eb3130fb36257619b98e52065683c8f204e5aa49c356ae04513`).
- 65 testes passaram localmente e no workflow de testes; `tools/validate_project.py` passou.
- Workflow de build/publicação: https://github.com/aoliveira07/smart-house-update-manager/actions/runs/37408427737

As alterações de código desta versão adicionam reconciliação automática para operações
que excedem o timeout, confirmação por job/versão, novas tentativas seguras com limite,
liberação do lock após esgotamento e diagnóstico estruturado de `RECOVERY` no Ingress.

## Histórico — 0.1.0

Repositório público: https://github.com/aoliveira07/smart-house-update-manager

Imagem pública: `ghcr.io/aoliveira07/smart-house-update-manager:0.1.0`

## Verificação

- 60 testes passaram localmente antes do envio.
- O workflow [Tests #1](https://github.com/aoliveira07/smart-house-update-manager/actions/runs/34728183087)
  concluiu com sucesso em Linux/Python 3.13.
- O workflow [Build and publish #1](https://github.com/aoliveira07/smart-house-update-manager/actions/runs/34728227781)
  passou pelos testes e construiu/publicou a imagem multiarch.
- Download anônimo do manifesto OCI confirmado para `linux/amd64` e `linux/arm64`
  (Home Assistant: amd64 e aarch64).
- Digest do índice publicado:
  `sha256:6de847eae1a90cdfea5a7572c1f503890c92f70d5414c52f2726d5baa460d59a`.
- Código usado no build: commit `8ecba6d566c1aaf3f7eacd960cd507824c2147b3`.
  A alteração posterior habilita a imagem no manifesto e atualiza a documentação;
  não altera o código executável da imagem.

## Instalação de homologação

1. No Home Assistant, abra a loja de Apps e o menu de repositórios.
2. Adicione `https://github.com/aoliveira07/smart-house-update-manager`.
3. Instale “Smart House Update Manager”.
4. **Antes de iniciar, configure `dry_run: true` nas opções do App.**
5. Inicie e abra o painel Ingress para revisar a classificação e o plano.
6. Siga a homologação em `smart_house_update_manager/DOCS.md` antes de migrar as
   automações existentes.

Publicação e build não equivalem à homologação de backup, updates ou reboot em
um Home Assistant real. Nenhuma automação existente foi alterada ou desativada.
