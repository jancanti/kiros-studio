# Fluxo de uma milestone

## 1. Retomar

Execute `python3 scripts/kiros_flow.py context`; leia o arquivo Mxx indicado. A primeira milestone não concluída é a única autorizada neste turno. Se todas estiverem concluídas, informe isso e pare. Se houver bloqueio registrado, confira se a condição mudou antes de retomar; não refaça chamadas caras ou ações falhas automaticamente.

Inspecione apenas código pertinente e o checkpoint anterior quando necessário. Se já há implementação, valide/reaproveite antes de construir. Use `docs/SPEC_INDEX.md` para localizar requisitos adicionais. Decisões locais não devem expandir escopo.

Execute `python3 scripts/kiros_flow.py start` para marcar início/retomada. Preserve trabalho parcialmente concluído. Em M00, escolha a stack e registre como instalar dependências, iniciar, testar e construir em `docs/DEVELOPMENT.md`. A origem não prescreve Next.js, ORM, Redis ou serviços extras.

## 2. Implementar com baixo custo

Use o menor conjunto de arquivos e abstrações necessário. Defina contratos e testes de comportamento relevante. Não transforme cada item em chamada LLM. Gere fixtures locais determinísticas e identifique resultados simulados na UI.

As variáveis `KIROS_PROVIDER_MODE=mock`, `KIROS_ALLOW_PAID_APIS=0`, `KIROS_ALLOW_PUBLISH=0` são um contrato para a aplicação, **não um bloqueio de rede do sistema operacional**. M00 deve implementar a recusa central; M02 deve testá-la em cada adaptador, inclusive fallback e retry. Não basta definir as variáveis. Mocks não eliminam o consumo normal da própria sessão Codex.

Consultas à documentação oficial para validar modelos/APIs são permitidas; teste real, geração paga e publicação precisam de autorização específica. Registre URLs/data em INTEGRATIONS.md. Não copie credenciais para evidências, logs ou frontend. Guardar a configuração não deve iniciar automaticamente uma requisição real.

## 3. Validar e registrar

Configure `docs/checks.json` na chave Mxx atual com uma lista não vazia de checks. Cada check contém `name`, `argv` (lista, sem shell) e `timeout_seconds` (1–3600). Exemplo de formato, após confirmar que esses comandos existem na stack:

```json
{"name":"testes relevantes", "argv":["npm","run","test","--","tests/campaign.test.ts"], "timeout_seconds":180}
```

Use comandos reais pertinentes à milestone: testes de comportamento, build quando necessário e smoke test que encerra sozinho. Não configure `echo`, no-op ou só os testes deste pacote como prova do aplicativo. Não crie testes que apenas espelham o código. Faça correções localizadas; repita validação somente quando necessário.

Preencha `docs/evidence/Mxx.json`: summary, critical_errors, limitations e cada ID acceptance com arquivos relativos existentes e descrição concreta da verificação (teste, cenário, resultado). Acrescente evidência visual para UI, quando pertinente. A lista de erros críticos só deve estar vazia se isso foi verificado. Atualize INTEGRATIONS.md distinguindo implementação, contratos simulados e validação ao vivo.

Execute `python3 scripts/kiros_flow.py checkpoint docs/evidence/Mxx.json`. O comando executa os checks, exige código zero, grava relatório, logs e hashes das evidências, atualiza o manifesto atomicamente e regenera STATUS.md. Falha mantém a milestone em andamento. Corrija e repita o checkpoint. Não rode os mesmos checks logo antes só para duplicar a validação.

O script verifica estrutura, arquivos e resultados dos comandos; a adequação dos testes e veracidade das evidências continuam responsabilidade do agente/revisor. Logs não devem conter segredos. O checkpoint não é um backup completo do código nem commit Git. Use versionamento existente se autorizado; nunca inclua arquivos do usuário indiscriminadamente. Backup do aplicativo pertence à M12.

## 4. Bloqueio ou conclusão

Se depender de credencial, autorização real ou informação indispensável, execute `python3 scripts/kiros_flow.py block "motivo concreto e próximo passo"`. Preserve evidências parciais; não marque como concluído. Para limites da sessão, deixe in_progress e registre o ponto de retomada na evidência. Evite loops ilimitados: se a mesma falha persistir após duas tentativas fundamentadas, registre causa e estado antes de insistir.

Na M12, só use real_readiness=true se as condições de uso real foram comprovadas. Integração suportada apenas por fixtures pode ser aceita em milestone intermediária quando claramente registrada; não autoriza declarar a V1 pronta para uso real. Se faltam permissões externas, finalize o trabalho local possível e registre o bloqueio.

Depois de um checkpoint aprovado, **pare**. Responda brevemente: milestone concluída, mudanças, testes/resultados e bloqueio ou limitação material. Uma nova mensagem `continue` retoma a próxima. Não criar automações recorrentes nem executar todas as milestones em um loop.
