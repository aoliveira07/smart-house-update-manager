# Smart House Update Manager — SH-005

Primeira entrega de código, versão **0.1.0**, para homologação em Home Assistant OS.
Centraliza manutenção às 04:00 e reboot diário às 05:30, ambos configuráveis.
O reboot ocorre mesmo sem atualizações, respeitando jobs críticos e o modo Dry Run.

O projeto inclui todos os arquivos completos, testes, painel Ingress, Dockerfile,
workflows para amd64/aarch64 e instruções para GHCR. Repositório:
https://github.com/aoliveira07/smart-house-update-manager.
Não houve instalação em Home Assistant nem alteração das seis automações existentes.

## Começar

1. Leia [o relatório da entrega](DELIVERY.md) e [a revisão técnica](AUDIT.md).
2. Consulte [a documentação operacional](smart_house_update_manager/DOCS.md).
3. Execute os testes em Python 3.12 ou 3.13:

   ```sh
   python -m venv .venv
   # Linux/macOS: . .venv/bin/activate
   # Windows PowerShell: .venv/Scripts/Activate.ps1
   python -m pip install -r requirements-dev.txt
   python -m pytest -q
   python tools/validate_project.py
   ```

4. Para instalação de homologação, adicione
   `https://github.com/aoliveira07/smart-house-update-manager` ao catálogo de
   repositórios de Apps do Home Assistant. Como alternativa, copie a pasta
   `smart_house_update_manager` para `/addons` de uma instalação de testes.
5. **Antes de iniciar o App, configure `dry_run: true` nas opções do Supervisor.**
   O padrão solicitado é `false`: iniciar depois das 04:00 pode iniciar manutenção
   de recuperação do horário perdido. O reboot também possui recuperação de horário,
   limitada aos 120 minutos de espera a partir das 05:30.
6. Abra o painel Ingress e siga a homologação descrita em DOCS.md.

## GitHub e imagens

O manifesto inicial não contém um endereço GHCR inventado: o Supervisor pode construir
a partir do Dockerfile. O workflow `build.yml` constrói uma imagem multiarch chamada
`ghcr.io/<owner>/<repository>:0.1.0` usando as coordenadas reais do repositório.

Depois da revisão e da criação do repositório, execute o workflow manualmente sem
publicar para validar o build. Para publicar, use a opção `publish` ou a tag `v0.1.0`.
Torne o pacote GHCR público para instalações sem autenticação. Só depois de a imagem
existir, execute:

```sh
python tools/prepare_registry.py SEU_OWNER SEU_REPOSITORIO
python tools/validate_project.py
```

O script regrava os manifests completos com `image` e URLs corretos. Não publica,
não faz commit e não transmite credenciais. O Dockerfile é a fonte do build; não há
`build.yaml`. A licença de distribuição deverá ser escolhida pelo proprietário
antes de uma publicação pública; esta entrega não atribui uma licença em seu nome.

## Conteúdo

- [Árvore completa](TREE.txt)
- [Arquitetura, segurança e compatibilidade](AUDIT.md)
- [Manual do App e migração](smart_house_update_manager/DOCS.md)
- [Resultados automatizados e limites da validação](DELIVERY.md)
- [Correspondência dos 30 cenários solicitados](TEST_MATRIX.md)

SH-005 permanece pendente de homologação real. A execução dos testes simulados não
comprova instalação, build Docker, permissões efetivas da instalação alvo ou reboot físico.

