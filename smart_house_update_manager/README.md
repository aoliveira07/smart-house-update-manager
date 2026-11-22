# Smart House Update Manager

![Smart House Update Manager](logo.png)

Home Assistant App para atualizar Apps, software/HACS, Core e OS com backup prévio,
histórico persistente, validação e reboot preventivo diário independente.

Versão 0.1.6 para homologação. Use `dry_run: true` antes de iniciar pela primeira vez.
Não desative as automações existentes até concluir os testes reais.

A versão 0.1.6 também reconhece entidades HACS que não registram explicitamente a
origem no entity registry, desde que exponham o contrato completo de release e update.
Operações que expiraram sem confirmação continuam em reconciliação segura, aguardando
jobs ativos e tentando novamente somente depois de provar que a operação anterior terminou.

O painel usa Ingress e é restrito aos administradores do Home Assistant. Não há
porta publicada na rede local. Firmware fica manual por padrão e UNKNOWN nunca é
instalado automaticamente. O Supervisor conserva seu próprio auto-update nativo.

Consulte [DOCS.md](DOCS.md) para configuração, limitações, recuperação e migração.

