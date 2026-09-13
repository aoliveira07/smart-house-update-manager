# Publicação — Smart House Update Manager 0.1.0

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
