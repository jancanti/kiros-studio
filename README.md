# KIROS Studio V1 — pacote de automação Codex

## Comece aqui

1. Extraia o ZIP e abra a pasta `kiros-codex-v1` como projeto no Codex.
2. Escreva **continue**.

O Codex implementa uma milestone, testa, atualiza o status e para. Quando quiser avançar, escreva **continue** novamente. `PROMPT_INICIAL.txt` está disponível caso você prefira um primeiro comando explícito.

Se já existe código do KIROS, use a pasta existente como projeto e peça ao Codex para incorporar os arquivos deste pacote preservando arquivos e instruções existentes. Não sobrescreva um AGENTS.md ou status anterior sem conciliar. Este pacote não altera automaticamente o projeto original.

## Pelo terminal (opcional)

Requisitos: macOS/Linux, Python 3.9+ e Codex CLI instalado/autenticado. O app dispensa a CLI, mas os scripts de status ainda precisam de Python. Na pasta do pacote:

```sh
./scripts/iniciar-codex
```

Para as próximas execuções:

```sh
./scripts/continuar-codex
```

Esse comando abre uma sessão interativa já instruída. Para execução não interativa use `./scripts/continuar-codex --exec`; é necessário um repositório Git reconhecido pela CLI. Inicialize o versionamento na pasta do projeto se ainda não existir. Permissões e autenticação do Codex continuam valendo; o script não as contorna. Não há loop automático entre milestones.

## O que está pronto

- 13 milestones, com critérios individuais e cobertura das 86 seções.
- Especificação original intacta e índice por seção.
- Um fluxo para iniciar, retomar, validar e registrar checkpoints.
- Status regenerado automaticamente e evidências por milestone.
- Testes locais do mecanismo de automação.

A fundação local do aplicativo está em `kiros/`: execute `python3 -m kiros` e abra
http://127.0.0.1:8765. Consulte `docs/DEVELOPMENT.md` para build, testes e limites.
O estado de cada milestone está em `docs/STATUS.md`. Nenhum provider real foi chamado.

## Consultar sem gastar uma sessão Codex

```sh
python3 scripts/kiros_flow.py status
python3 scripts/kiros_flow.py validate
python3 -m unittest discover -s tests -v
```

Os scripts não precisam de pacotes Python externos. `milestones.yaml` utiliza JSON, um subconjunto válido de YAML 1.2. O manifesto é a fonte única dos estados; STATUS.md pode ser reconstruído com o comando status.

Mocks são padrão no produto, e gastos/publicação reais continuam sujeitos a autorização. Isso não elimina o consumo da própria sessão Codex. Não prometemos uma porcentagem de economia: o pacote reduz releituras, replanejamento e execução repetida.

## Recuperação

Uma interrupção ou check com erro não avança a milestone. Use continue novamente. Se STATUS.md ficar desatualizado, rode status. Locks são liberados pelo sistema ao encerrar o processo; não há necessidade de apagar arquivos de lock. Use uma sessão por projeto, inclusive no app.

Checkpoints registram evidências e testes em docs/checkpoints; não substituem Git ou backup. Não faça commit de segredos ou logs com dados privados. Integrações simuladas e pendências reais ficam em docs/INTEGRATIONS.md. A M12 não declara prontidão real enquanto a validação necessária estiver pendente.

Consulte docs/CODEX_WORKFLOW.md para os detalhes destinados ao agente e docs/ORIGEM.md para a origem e documentação oficial utilizada.
