# Validação de integrações

M10 (2026-09-12): `InsightsService` usa SQLite real local. Observações competitivas
e avaliações de tendências são cadastradas pelo operador com fonte, data da
observação e data da análise. A descoberta por perfil/categoria/localização pesquisa
apenas essa base local; não há scraping, descoberta remota ou acesso autenticado a
concorrentes. Nenhuma API, LLM ou geração de imagem foi chamada nesta milestone.
Simulações são marcadas individualmente e excluídas das buscas por padrão.

O mapa usa dimensões informadas e metadados disponíveis do calendário em grupos
separados, sem tratar agendamento como publicação. Não infere fragrância, produto
ou atributos visuais ausentes. Fonte informada não significa fonte verificada.

Experimentos só iniciam acompanhamento local após autorização registrada. Não
executam geração nem publicação. Resultados A/B são contagens informadas com fonte,
taxas descritivas e confiança limitada; não há integração com Analytics ao vivo,
teste de significância, vencedor automático ou alteração da identidade oficial.
As capturas M10 usam banco temporário e dados fictícios identificados; não
representam desempenho ou análise de concorrentes reais.

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

M09 (2026-09-12): Calendário editorial inteligente e publicação controlada no Instagram
implementados segundo a documentação oficial vigente da Meta (Instagram Content Publishing API /
Graph API v20.0+). Operações cobrem criação de container de mídia, polling de status de
transcodificação, agendamento de post, checagem de cota de 25 posts/24h e auditoria pré-publicação
em 7 dimensões com bloqueio por falta de confirmação explícita (Seção 79).

### Documentação oficial do Instagram / Meta consultada em 2026-09-12:

1. **Instagram Content Publishing API (Meta Graph API v20.0+)**:
   - URL oficial: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/content-publishing
   - Endpoints oficiais verificados:
     - Criação de container: `POST https://graph.facebook.com/v20.0/{ig-user-id}/media`
     - Consulta de status de container: `GET https://graph.facebook.com/v20.0/{creation-id}?fields=status_code,status`
     - Publicação do container: `POST https://graph.facebook.com/v20.0/{ig-user-id}/media_publish`
     - Consulta de limites de cota: `GET https://graph.facebook.com/v20.0/{ig-user-id}/content_publishing_limit`
   - Requisitos de Conta:
     - Conta Instagram Professional (Business ou Creator) vinculada a uma Página do Facebook com acesso de administrador.
   - Permissões Meta necessárias:
     - `instagram_basic`: leitura básica do perfil profissional e identificador de conta.
     - `instagram_content_publish`: criação de containers e publicação de posts no feed, carrossel e Stories.
     - `pages_show_list`: listagem das páginas administradas pelo usuário para resolução do ID do Instagram.
     - `pages_read_engagement`: leitura de engajamento para fins de métricas operacionais.
   - Formatos e especificações técnicas suportadas:
     - Imagens de Feed: proporções 1:1 (quadrado), 4:5 (retrato vertical) ou 1.91:1 (paisagem); largura entre 320px e 1440px; tamanho máx 8 MB; formatos JPEG e PNG.
     - Imagens de Stories: proporção vertical 9:16 (1080x1920); tamanho máx 4 MB; formatos JPEG e PNG.
     - Carrosséis: entre 2 e 10 mídias com a mesma proporção.
   - Restrições e limitações operacionais da API oficial:
     - Limite de 25 posts por período móvel de 24 horas por conta.
     - Agendamento suportado oficialmente: mínimo 15 minutos e máximo 75 dias no futuro.
     - Ativos devem estar acessíveis publicamente via URL HTTPS válida durante o processamento.
     - A API não permite edição de legenda ou substituição de mídia após a publicação realizada.

| Integração M09 | Implementação | Contrato/fixture | Ao vivo | Pendência |
|---|---|---|---|---|
| Instagram Content Publishing | InstagramPublisher (`POST /media`, `GET /status`, `POST /media_publish`) | Fluxo operacional completo, agendamento, timezone-aware, reconciliação idempotente contra duplicidade e simulação de erro 503/429 | não testado | credenciais reais de App Meta e autorização explícita do usuário em M12 |
| Auditoria Pré-Publicação | PublicationAuditor (versão, fidelidade, copy, direitos, formatos, comercial e confirmação) | 7 dimensões validadas; recusa obrigatória sem confirmação humana explícita (Seção 79) | local determinístico | — |
| Calendário Inteligente | EditorialCalendarService (ritmo, pilares, saturação e datas prioritárias) | Frequência semanal, diversidade de pilares e rascunhos antecipados de datas sazonais sem oficialização sem aprovação | local determinístico | — |
| Recomendação de Horário | recommend_best_time com camadas (KIROS -> Setor -> Geral) | Três camadas de dados, nível de confiança, base explicada e prioridade irrevogável da escolha manual ("manual sempre vence") | local determinístico | — |

Nenhum post real foi disparado para contas ao vivo durante o desenvolvimento.
Toda a validação em ambiente local utilizou fixtures determinísticas e recusa central do gateway.
Segredos de autenticação nunca são registrados em logs nem retornados ao frontend.
