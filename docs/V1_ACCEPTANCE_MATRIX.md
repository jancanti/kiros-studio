# Matriz de Aceite Completo da V1 (Seções 81, 82 e 84)

Este documento cumpre o critério **M12-A03** e mapeia formalmente cada item das Seções 81 e 84 a evidências concretas no código e testes, além de registrar todos os grupos de testes obrigatórios da Seção 82 com seus respectivos comandos executados.

---

## 1. Mapeamento da Seção 81 — Critérios de Aceitação

| Área | Requisito da Seção 81 | Evidência no Código | Teste Automatizado |
|---|---|---|---|
| **Marca** | Configurar Brand Bible | `kiros/library.py` (`Library.save_brand_bible`) | `tests/test_library.py` |
| | Versionar Brand Bible | `kiros/library.py` (`brand_versions`) | `tests/test_library.py` |
| | Proteger regras de marca | `kiros/library.py` (`protect_rule`) | `tests/test_library.py` |
| | Aprovar alterações | `kiros/library.py` (`approve_brand_change`) | `tests/test_library.py` |
| **Produtos** | Cadastrar produtos | `kiros/library.py` (`create_product`) | `tests/test_library.py` |
| | Adicionar imagens de produto | `kiros/library.py` (`add_product_image`) | `tests/test_library.py` |
| | Analisar atributos | `kiros/library.py` (`analyze_product_photos`) | `tests/test_library.py` |
| | Criar Product Bible | `kiros/library.py` (`product_bibles`) | `tests/test_library.py` |
| | Classificar atributos (livre, protegido, crítico) | `kiros/library.py` (`set_attribute_protection`) | `tests/test_library.py` |
| | Versionar produto | `kiros/library.py` (`product_versions`) | `tests/test_library.py` |
| **Referências** | Adicionar referências | `kiros/library.py` (`add_reference`) | `tests/test_library.py` |
| | Analisar referências | `kiros/library.py` (`analyze_reference`) | `tests/test_library.py` |
| | Classificar escopo/tarefa/direitos | `kiros/library.py` (`classify_reference`) | `tests/test_library.py` |
| | Utilizar referências em campanhas | `kiros/campaigns/manager.py` | `tests/test_campaigns.py` |
| **Providers** | Cadastrar provedores de IA | `kiros/providers.py` (`ProviderManager.register`) | `tests/test_providers.py` |
| | Testar conexão/credenciais | `kiros/providers.py` (`test_provider`) | `tests/test_providers.py` |
| | Ativar provedores | `kiros/providers.py` (`activate_provider`) | `tests/test_providers.py` |
| | Desativar provedores | `kiros/providers.py` (`deactivate_provider`) | `tests/test_providers.py` |
| | Escolher modelo homologado | `kiros/providers.py` (`VALID_MODELS`) | `tests/test_providers.py` |
| **Campanhas** | Criar campanha | `kiros/campaigns/manager.py` (`create_campaign`) | `tests/test_campaigns.py` |
| | Planejar campanha | `kiros/campaigns/manager.py` (`plan_campaign`) | `tests/test_campaigns.py` |
| | Selecionar objetivo oficial | `kiros/campaigns/manager.py` (`VALID_OBJECTIVES`) | `tests/test_campaigns.py` |
| | Selecionar produtos | `kiros/campaigns/manager.py` (`select_products`) | `tests/test_campaigns.py` |
| | Gerar storyboard | `kiros/campaigns/manager.py` (`create_slide`) | `tests/test_campaigns.py` |
| | Configurar pipeline | `kiros/campaigns/manager.py` (`update_pipeline_config`) | `tests/test_campaigns.py` |
| | Estimar custo prévio | `kiros/campaigns/manager.py` (`estimate_campaign_cost`) | `tests/test_campaigns.py` |
| | Aprovar campanha | `kiros/campaigns/manager.py` (`approve_campaign`) | `tests/test_campaigns.py` |
| | Executar campanha | `kiros/execution/queue.py` (`enqueue_campaign`) | `tests/test_execution.py` |
| **Imagens** | Gerar imagens | `kiros/execution/queue.py` (`Worker.run_once`) | `tests/test_execution.py` |
| | Utilizar referências | `kiros/execution/queue.py` (`ExecutionJob`) | `tests/test_execution.py` |
| | Selecionar engine | `kiros/router.py` (`ImageEngineRouter`) | `tests/test_router.py` |
| | Combinar engines | `kiros/router.py` (`select_engine`) | `tests/test_router.py` |
| | Validar fidelidade visual | `kiros/fidelity/service.py` (`check_fidelity`) | `tests/test_fidelity.py` |
| | Regenerar somente slide afetado | `kiros/execution/queue.py` (`regenerate_slide`) | `tests/test_execution.py` |
| **Layout** | Aplicar templates | `kiros/layout/templates.py` (`TemplateLibrary`) | `tests/test_layout_engine.py` |
| | Montar composição SVG | `kiros/layout/engine.py` (`render_svg`) | `tests/test_layout_engine.py` |
| | Inserir texto e tipografia Rubik | `kiros/layout/elements.py` (`HeadlineElement`) | `tests/test_layout_engine.py` |
| | Inserir logo da marca | `kiros/layout/elements.py` (`LogoElement`) | `tests/test_layout_engine.py` |
| | Editar layout visual | `kiros/layout/editor.py` (`LayoutEditor`) | `tests/test_layout_http.py` |
| | Proteger atributos visuais | `kiros/layout/engine.py` (`validate_safe_areas`) | `tests/test_layout_engine.py` |
| **Conteúdo** | Criar legenda sem clichês | `kiros/content/copy_engine.py` (`generate_automatic_caption`) | `tests/test_copy_engine.py` |
| | Criar sequência de Stories | `kiros/content/stories_engine.py` (`plan_sequence`) | `tests/test_stories_engine.py` |
| | Controlar CTA sem fórmulas | `kiros/content/copy_engine.py` (`check_prohibited_elements`) | `tests/test_copy_engine.py` |
| | Respeitar voz brasileira | `kiros/content/copy_engine.py` | `tests/test_copy_engine.py` |
| **Calendário** | Visualizar calendário | `kiros/calendar/service.py` (`list_entries`) | `tests/test_calendar_service.py` |
| | Organizar publicações | `kiros/calendar/service.py` (`create_entry`) | `tests/test_calendar_service.py` |
| | Recomendar horários | `kiros/calendar/service.py` (`recommend_best_time`) | `tests/test_calendar_service.py` |
| | Registrar decisão humana | `kiros/calendar/service.py` (`record_time_decision`) | `tests/test_calendar_service.py` |
| **Histórico** | Versionar execuções | `kiros/execution/queue.py` (`execution_versions`) | `tests/test_execution.py` |
| | Comparar até 3 versões | `kiros/execution/queue.py` (`compare_versions`) | `tests/test_fidelity.py` |
| | Restaurar versão anterior | `kiros/execution/queue.py` (`restore_version`) | `tests/test_fidelity.py` |
| | Registrar custo e engine | `kiros/execution/queue.py` (`actual_cost_usd`, `engine`) | `tests/test_execution.py` |
| | Registrar decisão e proveniência | `kiros/director/memory.py` (`record_decision`) | `tests/test_memory.py` |
| **Inteligência** | Recomendar direções criativas | `kiros/ideas.py` (`CreativeDirectorService`) | `tests/test_ideas.py` |
| | Detectar saturação | `kiros/insights.py` (`InsightsService.saturation`) | `tests/test_insights.py` |
| | Analisar tendências de mercado | `kiros/insights.py` (`record_competitor`, `discover`) | `tests/test_insights.py` |
| | Aprender com correções | `kiros/learning.py` (`record_campaign_correction`) | `tests/test_learning_and_prompts.py` |
| | Manter memória contextual | `kiros/director/memory.py` (`MemoryStore`) | `tests/test_memory.py` |

---

## 2. Mapeamento da Seção 82 — Grupos de Testes Obrigatórios

Todos os grupos de testes da Seção 82 foram executados e validados por suites automatizadas:

| Grupo Seção 82 | Cenários Cobertos | Comando Executado | Resultado |
|---|---|---|---|
| **Estratégia** | Criação de campanha, objetivos oficiais, pilares, seleção de produto sem dados comerciais e detecção de conflitos | `python3 -m unittest tests/test_campaigns.py tests/test_ideas.py` | 27 testes OK |
| **Providers** | Conexão, erros estruturados (400, 500), timeout, credencial inválida (401) e provedor indisponível (503) | `python3 -m unittest tests/test_providers.py tests/test_providers_http.py` | 13 testes OK |
| **Geração** | Fila de execução, concorrência thread-safe, retry com backoff, cancelamento com impacto, pausa e retomada | `python3 -m unittest tests/test_execution.py tests/test_execution_http.py` | 16 testes OK |
| **Fidelidade** | Produto correto, produto alterado, etiqueta alterada, logo alterado e sensibilidade ao threshold | `python3 -m unittest tests/test_fidelity.py tests/test_fidelity_http.py` | 10 testes OK |
| **Custos** | Estimativa prévia, orçamento mensal, aprovação antes de gastar, limite e cálculo de custo real | `python3 -m unittest tests/test_cost_manager.py tests/test_token_economy.py` | 12 testes OK |
| **Layout** | Formatos 4:5 e 9:16, tipografia Rubik, proporção de logo bloqueada, elementos semânticos e proteção de safe areas | `python3 -m unittest tests/test_layout_engine.py tests/test_layout_http.py` | 12 testes OK |
| **Memória** | Recuperação seletiva por escopo, compactação por orçamento de tokens, relevância e rastreabilidade de proveniência | `python3 -m unittest tests/test_memory.py` | 5 testes OK |
| **Versionamento**| Criação de versões de execução, comparação lado a lado (até 3), restauração segura e preservação de histórico | `python3 -m unittest tests/test_fidelity.py tests/test_execution.py` | 16 testes OK |
| **Regressão Global**| Execução integrada de todos os testes da aplicação | `python3 -m unittest discover -s tests -v` | **224 testes OK** |

---

## 3. Mapeamento da Seção 84 — Definition of Done (28 Requisitos)

| # | Requisito da Seção 84 | Status | Evidência Concreta |
|---|---|---|---|
| 1 | Projeto inicia corretamente | Concluído | `python3 -m kiros --port 8765` inicializa servidor HTTP nativo |
| 2 | Interface funciona | Concluído | Rotas `/inicio`, `/campanhas`, `/biblioteca`, `/calendario`, `/insights`, `/configuracoes` validadas em `scripts/smoke.py` |
| 3 | SQLite funciona | Concluído | Migrações 001 a 012 executadas com schema transacional integro |
| 4 | Filesystem funciona | Concluído | `FileStorage` armazena e recupera referências, imagens e backups |
| 5 | Providers podem ser configurados | Concluído | `/configuracoes` permite salvar Gemini, OpenAI, Firefly e Custom |
| 6 | Providers podem ser testados | Concluído | `POST /api/providers/test` executa validação mock sem vazar segredos |
| 7 | Produtos podem ser cadastrados | Concluído | `Library.create_product` e interface `/biblioteca` cadastram produtos |
| 8 | Brand Bible funciona | Concluído | Brand Bible com regras de tom, pilares e versionamento implementada |
| 9 | Product Bible funciona | Concluído | Atributos livres, protegidos e críticos classificados e auditados |
| 10 | Campanhas podem ser criadas | Concluído | Fluxo de briefing, objetivo e geração de campanha operacional |
| 11 | Storyboard pode ser criado | Concluído | Slides com formato, composição, texto e referências gerenciados |
| 12 | Pipeline pode ser configurado | Concluído | Modos minimal, step_by_step e full_control com etapas explícitas |
| 13 | Custo pode ser estimado | Concluído | `CostManager` calcula custo estimado antes de qualquer autorização |
| 14 | Aprovação funciona | Concluído | Aprovação formal vinculada à versão do plano; mudanças invalidam aprovação |
| 15 | Geração funciona | Concluído | Fila de execução processa jobs com workers determinísticos |
| 16 | Fidelity Check funciona | Concluído | `ProductFidelityService` avalia 8 dimensões e compara com produto real |
| 17 | Layout Engine funciona | Concluído | Composição SVG determinística com tipografia Rubik, sem cortes |
| 18 | Copy funciona | Concluído | `CopyEngine` gera legendas na voz brasileira sem emojis/clichês de IA |
| 19 | Versões funcionam | Concluído | `ExecutionVersion` persiste histórico imutável para cada slide |
| 20 | Comparação funciona | Concluído | Comparação visual lado a lado de até 3 versões suportada |
| 21 | Cancelamento funciona | Concluído | Cancelamento de slide ou fila com transparência de custos debitados |
| 22 | Pausa funciona | Concluído | Fila pausa imediatamente sem perda de estado dos jobs em execução |
| 23 | Retomada funciona | Concluído | Retomada de fila preserva ordem e prioridade dos jobs |
| 24 | Calendário funciona | Concluído | Calendário com ritmo semanal, saturação e sugestão de horários |
| 25 | Busca funciona | Concluído | Busca global insensível a acentos cobrindo 8 tipos de entidade |
| 26 | Memória funciona | Concluído | `MemoryStore` com 6 tipos de memória e proveniência obrigatória |
| 27 | Testes automatizados passam | Concluído | **224 testes unitários e de integração aprovados (0 falhas)** |
| 28 | Nenhum erro crítico conhecido permanece | Concluído | Verificado via `scripts/smoke.py`, `scripts/build.py` e bateria de testes |
