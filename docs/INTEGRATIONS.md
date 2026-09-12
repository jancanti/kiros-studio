# Validação de integrações

M00 (2026-09-12): fundação local implementada; nenhuma integração externa testada ao vivo.
Dez contratos definidos em `kiros/core/contracts.py`; MockLLM determinístico e
gateway central com recusa antes do transporte. SQLite e filesystem reais locais;
demais portas ainda sem adaptadores. Nenhum modelo/API selecionado nesta milestone,
portanto não houve consulta de documentação de providers nem consumo pago.

| Integração | Implementação | Contrato/fixture | Ao vivo | Pendência |
|---|---|---|---|---|
| LLM | somente MockLLM | contrato e injeção testáveis localmente | não testado | adaptadores M02; estratégia M03 |
| Gemini Image | pendente | pendente | não testado | M02/M05 |
| OpenAI Image | pendente | pendente | não testado | M02/M05 |
| Firefly Image | pendente | pendente | não testado | M02/M05 |
| Custom Image | pendente | pendente | não testado | M02 |
| Instagram/Analytics | pendente | pendente | não testado | M09/M10 |

O agente atualiza esta matriz com documentação oficial/data, modelos confirmados, limitações, cenários executados e autorização quando houver validação real. Não registrar credenciais. Diferenciar adaptador implementado, contrato simulado e teste ao vivo bem-sucedido.

M01 (2026-09-12): SQLite/filesystem reais locais agora persistem marca, produtos,
estoque, vendas e referências. Importador CSV implementado e validado por cenários
locais, incluindo rollback do lote e dados ausentes. Sem sincronização comercial.

| Integração M01 | Implementação | Contrato/fixture | Ao vivo | Pendência |
|---|---|---|---|---|
| Visão de produto/referência | VisionProvider + MockVision injetado | PNG técnico, atributos não verificados, resultado simulado e proposta sem aprovação automática | não testado | adaptador real e validação autorizada em M02 |
| Vendas CSV | importador local transacional | dados fictícios com ausências, zeros, inválidos e reenvio | arquivo comercial não usado | importar arquivo real pelo usuário |
| Estoque manual | cadastro/contagem com origem e histórico | valores de teste, NULL distinto de zero | contagem comercial não usada | entrada do usuário |

Nenhuma documentação de API foi necessária: M01 não escolhe provider/modelo.
Nenhuma chamada externa, geração de imagem, API paga ou publicação foi realizada.
Mock não substitui adaptadores reais nem comprova fidelidade visual de produtos.

M02 (2026-09-12): Adaptadores de motores de imagem implementados segundo a documentação
oficial vigente, com validação estrita de IDs e endpoints reais. Mocks determinísticos
cobrem conexão, latência, erros HTTP (400, 500), credenciais inválidas (401),
indisponibilidade (503) e timeout. ExternalGateway bloqueia qualquer egress no modo mock.

### Documentação oficial e modelos vigentes consultados em 2026-09-12:

1. **Google Gemini / Imagen 3**:
   - URL oficial: https://ai.google.dev/gemini-api/docs/imagen
   - Endpoint oficial: `https://generativelanguage.googleapis.com/v1beta/models`
   - Modelos verificados: `imagen-3.0-generate-002` (Qualidade padrão, $0.030/img) e `imagen-3.0-fast-generate-001` (Rápido, $0.020/img).
   - IDs presumidos banidos: nenhum modelo inexistente aceito.

2. **OpenAI DALL-E**:
   - URL oficial: https://platform.openai.com/docs/api-reference/images/create
   - Endpoint oficial: `https://api.openai.com/v1/images/generations`
   - Modelos verificados: `dall-e-3` ($0.040/img standard) e `dall-e-2` ($0.020/img).

3. **Adobe Firefly Services**:
   - URL oficial: https://developer.adobe.com/firefly-api/docs/guides/api/image_generation/
   - Endpoint oficial: `https://firefly-api.adobe.io/v3/images/generate`
   - Modelos verificados: `firefly-image-3` ($0.040/crédito) e `firefly-image-2` ($0.040/crédito).

4. **CustomImageProvider**:
   - Suporte a endpoint HTTP configurável, cabeçalhos de autenticação e modelo arbitrário (não vazio).

| Integração M02 | Implementação | Contrato/fixture | Ao vivo | Pendência |
|---|---|---|---|---|
| Gemini Image | GeminiImageEngine (`imagen-3.0-generate-002`, `imagen-3.0-fast-generate-001`) | Sucesso (200), erro (400), timeout, 401 (chave inválida), 503 e medição de latência via mock determinístico | não testado | chave de API real e autorização de consumo em M05/M12 |
| OpenAI Image | OpenAIImageEngine (`dall-e-3`, `dall-e-2`) | Conexão, geração simples, 401 e latência validados via mock determinístico | não testado | chave de API real e autorização de consumo em M05/M12 |
| Firefly Image | FireflyImageEngine (`firefly-image-3`, `firefly-image-2`) | Conexão, geração simples, timeout e latência validados via mock determinístico | não testado | credenciais Adobe Console e autorização de consumo em M05/M12 |
| Custom Image | CustomImageProvider (endpoint/modelo configuráveis) | Conexão, geração simples e latência validados via mock determinístico | não testado | endpoint externo fornecido pelo usuário |
| Roteador de Motores | ImageEngineRouter com recomendação e overrides | Cenários ambient, conceptual, studio e economy com prioridade manual comprovada | local determinístico | — |
| Gestão de Custos e Budget | CostManager com estimativas, gastos reais e reservas atômicas | Transações SQLite imediatas, concorrência segura entre threads, alertas e bloqueio de limite | local determinístico | — |
| Economia de Tokens | ContextOptimizer com Brand/Product seletivo, orçamento e cache | Deduplicação por hash, invalidação por entidade e recusa de gasto com preço desconhecido | local determinístico | — |

Nenhuma chamada externa real, cobrança em cartão ou consumo de cotas pagas foi executado.
Toda a validação em ambiente local utilizou fixtures determinísticas e recusa central do gateway.
Segredos de autenticação nunca são registrados em logs nem retornados ao frontend.
