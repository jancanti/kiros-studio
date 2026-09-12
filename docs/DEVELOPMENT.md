# Desenvolvimento local — M00

## Stack e execução

Python 3.9+ com biblioteca padrão: HTTP server local, HTML renderizado no servidor,
CSS, SQLite e filesystem. Nenhuma dependência precisa ser instalada. A escolha
aproveita o Python já exigido pelo fluxo e evita serviços ou toolchains extras.

Na raiz do projeto:

```sh
python3 -m kiros
```

Abra http://127.0.0.1:8765. Encerre com Ctrl+C. Porta alternativa e armazenamento:

```sh
python3 -m kiros --port 8766 --data-dir /private/tmp/kiros-local
```

Dados padrão: `.kiros/studio.sqlite3` e `.kiros/files/`. O nome do espaço pode ser
salvo em Configurações; persiste após reinício e não altera a identidade oficial.
Cada conexão SQLite é curta; migrações numeradas em `kiros/migrations/` são
aplicadas uma vez, com transação e tabela de versões. Arquivos ficam fora do banco.

```sh
python3 scripts/build.py
python3 -m unittest discover -s tests -v
python3 scripts/smoke.py
```

Build valida a sintaxe e gera `dist/kiros-studio.zip` com Python, CSS e SQL.
Extraia em uma pasta e execute `python3 -m kiros` nela. O smoke usa dois processos
de servidor, porta efêmera e dados temporários, verifica HTTP e persistência e
encerra sozinho. Em sandbox é necessária permissão para abrir porta de loopback.
No fluxo de milestone, não repita esses comandos antes do checkpoint: ele os executa.

## Limites da fundação

UI → Application → CreativeDirector/contratos → providers/infraestrutura.
As dez portas estão em `kiros/core/contracts.py`. O Director recebe `LLMProvider`
por injeção e não importa implementações. Apenas SQLite, filesystem e MockLLM têm
implementação nesta etapa. Nenhuma criação de campanha ou integração real existe.

`Policy.from_env()` assume mock, APIs pagas e publicação desabilitadas. `.env.example`
documenta variáveis de shell; não há carregamento implícito de `.env`. M00 sempre
conecta MockLLM, mesmo com configuração live. `ExternalGateway.call` é o ponto
obrigatório para adaptadores externos: mock recusa antes de executar o transporte;
live exige permissões e aprovação específica para gasto/publicação. É um contrato
de aplicação, não firewall. M02 deverá cobrir cada adaptador, fallback e retry.

Segredos são valores privados com representação redigida; nunca usar `asdict` nem
serializar configurações. API usa lista explícita de campos públicos. Erros externos
são sanitizados e o servidor não registra URLs/payloads. Credenciais não são coletadas
pela UI da M00. Arquivos usam escrita atômica e caminhos relativos sem traversal ou
symlinks; pressupõe diretório de dados sob controle do usuário local confiável.
Não protege contra outro processo malicioso com acesso à mesma conta.

Servidor escuta somente loopback, valida Host e Origin em gravações e usa CSP.
Não é servidor para publicação na Internet. Proveniência exige origem conhecida,
referência não vazia e data com timezone. Somente preferências e versão de schema
são persistidas; não são criadas tabelas especulativas.

## Direção da interface

Base KIROS: papel `#f5f3ee`, verde profundo `#273b32`, texto secundário `#59685e`,
sálvia `#e5eade`, superfície `#fffefa`, linhas `#cbd1c8`. Georgia em títulos e Arial
na navegação mantêm leitura local sem baixar fontes. Marca tipográfica espaçada,
coluna lateral discreta e mensagem “Intenção antes da criação” refletem a direção
editorial da especificação; sem fotografias geradas, métricas ou produtos inventados.
Navegação vira grade no mobile. Links nativos, foco visível, skip link, rótulos e
`aria-current` compõem a base acessível. Sem animações.

## M01 — Marca, produtos e referências

Use **Marca** para cadastrar produtos, contar estoque, importar CSV, propor fichas
completas da marca/produto, aprovar versões e definir overrides. Em **Biblioteca**,
envie PNG/JPEG (até 5 MB por arquivo), informe origem/direitos/ângulo/qualidade e
vincule ao produto ou à campanha. Com 3–5 referências, crie uma proposta visual
simulada; revise em Marca. Não aprove valores simulados como dados reais.
A API HTTP interna usa os mesmos formulários, valida Origin e Host e aceita no
máximo 6 MB por envio. Arquivos ficam no filesystem com hash do conteúdo; nomes
recebidos nunca se tornam caminhos. Imagens são servidas por ID com MIME fixo,
CSP e nosniff. A validação de imagem nesta etapa reconhece assinaturas PNG/JPEG;
não substitui decodificação ou inspeção de imagem no provider futuro.

CSV UTF-8 (BOM aceito), vírgula, cabeçalho exato:

```csv
product_id,date,quantity,revenue
produto-existente,2026-09-01,2,
```

O exemplo é formato, não dado comercial. Produto e data válidos e quantidade
inteira não negativa são obrigatórios. Receita aceita até duas casas decimais com
ponto; vazio vira NULL, zero é preservado. Lote inválido é rejeitado por inteiro,
e reenvio de conteúdo idêntico é recusado por hash. Arquivos diferentes com vendas
sobrepostas exigem revisão do usuário: não há identificador de transação na V1
manual. Importação não infere nem altera estoque. Cadastro e histórico de contagem
mantêm proveniência, assim como lotes CSV, referências e versões.

`002_library.sql` adiciona apenas entidades da M01. `kiros/library.py` concentra
transações e invariantes; UI não escreve diretamente no banco. Propostas imutáveis
armazenam a versão oficial base. Aprovação identifica responsável/data e recusa
propostas desatualizadas. Alteração ou remoção de protected requer confirmação;
critical não pode mudar valor nem ser rebaixado/removido após aprovação. `free`
pode variar, mas oficialização continua exigindo aprovação. A proposta é uma ficha
completa, não um patch. Overrides são substituições locais de campos não vazios,
fixados na versão global aprovada do momento; salvar novamente substitui o override
anterior. Apenas o identificador de campanha é usado, sem antecipar o fluxo M03.

Reference Set ordena por ângulos adequados à tarefa, qualidade manual e ID como
desempate, até 5 fotos; a primeira é a recomendada. Override manual preserva a ordem
e valida produto/escopo. Seleção é feita sob demanda, sem salvar um briefing futuro.
Origem external/unknown ou direitos desconhecidos sempre geram inspiration_only.
A marcação comercial nunca é inferida da imagem. `VisionProvider` recebe bytes,
retorna atributos e origem/simulação. `MockVision` não interpreta pixels: retorna
atributos não verificados, não inventa materiais e não oficializa a resposta.
Adaptador real de visão fica para a integração M02; sem validação ao vivo nesta etapa.

A M01 mantém a paleta, Georgia/Arial e navegação da M00. Fichas oficiais precedem
formulários recolhidos, com histórico e aprovação separados. Sem imagens geradas.
As capturas usam dados explicitamente fictícios em diretório temporário, nunca o
armazenamento comercial. Testes unitários e HTTP exercitam aprovação, isolamento,
CSV, upload, seleção, simulação, escaping e persistência; checkpoint faz a execução
final junto ao build e ao smoke de reinício de processos.

## M02 — Providers, roteamento e controle de gastos

A M02 implementa a arquitetura de provedores de geração de imagem, o roteamento
inteligente de motores e o controle rígido de custos e tokens:

1. **Catálogo oficial de modelos** (`kiros/providers/catalog.py`):
   - Modelos verificados contra a documentação oficial vigente em 2026-09-12.
   - Google Gemini (Imagen 3): `imagen-3.0-generate-002` e `imagen-3.0-fast-generate-001`.
   - OpenAI (DALL-E): `dall-e-3` e `dall-e-2`.
   - Adobe Firefly Services: `firefly-image-3` e `firefly-image-2`.
   - Provedor customizado (`custom`): endpoint, modelo e cabeçalhos arbitrários.
   - Rejeição estrita de IDs presumidos ou modelos inexistentes.

2. **Adaptadores de imagem** (`kiros/providers/engines.py`):
   - `GeminiImageEngine`, `OpenAIImageEngine`, `FireflyImageEngine`, `CustomImageProvider`.
   - Todas as requisições passam por `ExternalGateway.call`, que recusa chamadas
     no modo mock antes de qualquer transporte de rede.
   - Mocks determinísticos cobrem conexão bem-sucedida, erro HTTP (400, 500),
     timeout, chave de API inválida (401) e indisponibilidade (503).
   - Medição precisa de latência em milissegundos.
   - Sanitização de mensagens de erro garante que nenhuma chave de API vaze.

3. **Gerenciador de provedores e tela** (`kiros/providers/manager.py`, `kiros/ui/providers.py`):
   - Cadastro, atualização, ativação/desativação e exclusão persistidos em SQLite.
   - Credenciais salvas nunca retornam ao frontend nem a logs (exibidas como `••••••••`).
   - Botões para testar conexão e executar teste simples de geração com exibição
     de status (Sucesso/Erro), latência em ms e mensagem sanitizada.

4. **Image Engine Router** (`kiros/providers/router.py`):
   - Recomendação automática avaliando contexto do slide (ambient, conceptual, studio, economy),
     com motivo, custo estimado por imagem, confiança e alternativas avaliadas.
   - Configuração de motor padrão por campanha e override por slide.
   - Prevalência manual estrita: override do slide > padrão da campanha > recomendação automática.

5. **CostManager e Budget** (`kiros/cost.py`):
   - Separação clara entre custo estimado e custo real.
   - Rastreamento por campanha, asset, etapa, provedor, modelo, quantidade e data/hora.
   - Avaliação prévia antes de operações caras: Plano, Custo, Impacto, Confiança, Alternativas, Aprovação.
   - Reserva atômica de orçamento (`reserve_budget`) com proteção contra condições de
     corrida em concorrência; ultrapassar limite exige aprovação explícita.
   - Conclusão da reserva (`commit_reservation`) e liberação (`release_reservation`).

6. **Economia de tokens e regra de contexto** (`kiros/context.py`):
   - Recuperação seletiva de Brand Bible e Product Bible (apenas atributos necessários).
   - Compactação e aplicação de orçamento estrito de caracteres/tokens.
   - Deduplicação por hash e cache com invalidação por entidade.
   - Recusa de gasto se o preço for desconhecido ou a estimativa falhar.

## M03 — Creative Director, ideias e contexto

A M03 implementa o núcleo estratégico do KIROS Studio, integrando o Creative Director, o Banco de Ideias, a governança de pilares editoriais, o planejamento sazonal antecipado, a memória tipada e a detecção de conflitos:

1. **Creative Director e Briefing Híbrido** (`kiros/core/director.py`, Seções 9, 11 e 12):
   - Serviço central de orquestração estratégica onde modelos de IA atuam estritamente como ferramentas.
   - Entrada livre estruturada progressivamente (`interpret_briefing`), gerando dados confirmáveis e formulando apenas perguntas mínimas agrupadas por afinidade temática (sem questionários longos).
   - Matriz de recomendação de objetivos com objetivo primário, secundário, justificativa e nível de confiança percentual (suporte a `vendas`, `lançamento`, `awareness`, `engajamento`, `relacionamento`, `educação`, `tráfego`, `sazonal` e `personalizado`).
   - Seleção de produtos do catálogo para conceitos criativos baseada puramente em afinidade visual e conceitual, sem depender de dados comerciais de vendas ou faturamento (`select_products_for_concept`).
   - Decisões estratégicas registradas no banco com proveniência explícita (`user`, `creative_director`).

2. **Banco de Ideias, Pilares e Governança Editorial** (`kiros/director/ideas.py`, Seções 13, 14, 15 e 16):
   - Seis pilares editoriais de conteúdo pré-configurados: `produtos`, `lifestyle`, `marca`, `educativo`, `relacionamento` e `comercial`.
   - Propostas de novos pilares (`propose_new_pillar`) registradas como rascunho pendente de confirmação; nunca criadas oficialmente sem aprovação explícita do usuário.
   - Teto rígido de governança de até 5 ideias ativas por pilar (máximo de 30 ideias ativas simultâneas no sistema).
   - Estados de ideia: `suggested`, `approved`, `rejected`, `scheduled`, `published`, `archived`, `pinned`.
   - Suporte a fixação (`pinned`) e rejeição com motivo obrigatório registrado.
   - Algoritmo de assinatura normalizada (fingerprint) que bloqueia reapresentação superficial de ideias previamente rejeitadas no mesmo pilar.
   - Gerador de conteúdo de descoberta adjacente (`generate_adjacent_content_suggestions`) detalhando por que atrai o público, qual a relação com a KIROS e a ponte concreta para a marca.
   - Radar de oportunidades sazonais (`get_seasonal_opportunities`) focado em Natal e Dia das Mães, acionado 2 a 3 meses antes da data com 4 fases de campanha (`Warm-up`, `Consideração`, `Conversão`, `Last Call`), operando como rascunho sem oficialização automática no calendário sem aprovação.

3. **Memória Tipada e Resolução de Conflitos** (`kiros/director/memory.py`, Seções 48 e 49):
   - Gerenciador `MemoryStore` com 6 tipos estruturados: `campaign_context`, `recurring_preference`, `brand_rule`, `commercial_data`, `creative_decision`, `operational_setting`.
   - Recuperação seletiva (`retrieve_relevant_context` / `query_memories`) que busca apenas o contexto relevante para a tarefa, evitando despejar toda a base na janela de contexto.
   - Compactação e orçamento de memória (`compact_memories`) para economia de tokens e normalização de espaços.
   - Detecção de conflitos (`detect_conflicts`) entre dados candidatos e a Brand Bible / Product Bible oficiais, classificando por impacto (`critical`, `protected`, `free`), apontando as fontes de cada informação e fornecendo recomendações claras.
   - Invariante de integridade: informações candidatas nunca sobrescrevem dados oficiais de marca ou produto automaticamente.

4. **Interface e HTTP do Creative Director** (`kiros/ui/creator.py`, `kiros/__main__.py`):
   - Rota `/criar` com formulário de briefing híbrido, painel de diretrizes estruturadas, contadores visuais de ideias ativas por pilar, cartões com status e ações (fixar, rejeitar com motivo), sugestões adjacentes e radar sazonal.
   - Endpoints sob `/api/creator/*` protegidos contra CSRF, verificação estrita de Origin/Host e formato `application/x-www-form-urlencoded`.

## M04 — Campanha, storyboard e aprovação

A M04 implementa o fluxo principal de campanhas, storyboard por slide, pipeline de execução multi-engine e o sistema rigoroso de aprovação (Seções 10, 23, 31, 56, 66, 75 da especificação):

1. **Ciclo de Vida e Persistência de Campanhas** (`kiros/campaigns/models.py`, `kiros/campaigns/manager.py`, Seções 10 e 66):
   - Migração `005_campaigns_storyboard_and_approval.sql` com tabelas relacionais `campaigns`, `storyboard_slides`, `pipeline_steps` e `campaign_approvals`.
   - Estados explícitos de execução: `draft`, `awaiting_approval`, `approved`, `queued`, `running`, `validating`, `completed`, `failed`, `paused`, `cancelled`, `archived`.
   - Persistência estruturada em SQLite de briefing interpretado, estratégia, produtos vinculados, storyboard e pipeline.
   - Versionamento rigoroso do plano (`plan_version`) iniciado em 1 e incrementado a cada alteração material.

2. **Storyboard por Slide e Pipeline Multi-Engine Mínimo** (Seções 23 e 31):
   - Cada slide possui enquadramento (`wide`, `medium`, `detail`, `close-up`, `overhead`), prompt visual detalhado, rascunho de legenda e motor de imagem dedicado.
   - Regra da Seção 23: menor número de etapas necessário para máxima qualidade, evitando degradação e custos desnecessários (por padrão, 1 etapa concisa de geração por slide).
   - Suporte a multi-engine na mesma campanha com resolução hierárquica: override explícito do slide > recomendação do router > Gemini Imagen 3 padrão.
   - Edição localizada do pipeline (`update_pipeline_step`): alterar uma etapa preserva integralmente todas as etapas e slides não afetados.

3. **Tela de Aprovação Rigorosa** (`kiros/ui/campaigns.py`, Seção 75):
   - Rota `/conteudo?campaign_id={id}` apresentando o painel unificado com todos os campos mandatórios:
     - Objetivo (primário e secundário em destaque).
     - Conceito e briefing detalhado.
     - Produtos selecionados do catálogo.
     - Storyboard completo com visualização por cartão.
     - Motores e etapas do pipeline com seus custos unitários.
     - Resumo quantitativo: gerações estimadas, custo total estimado em R$ e nível de confiança (%).
     - Ações explícitas de governança: `[Aprovar Execução]`, `[Cancelar Campanha]` e controles de edição localizada.

4. **Modos de Aprovação e Vinculação Orçamentária** (Seção 56):
   - Suporte aos três modos da especificação:
     - `minimal`: aprovação conjunta de todo o plano de execução.
     - `step_by_step`: aprovação progressiva de cada etapa individual do pipeline.
     - `full_control`: aprovação minuciosa de cada etapa e slide antes da execução.
   - Registro formal na tabela `campaign_approvals` vinculando a aprovação ao `plan_version`, custo estimado, aprovador, proveniência e data/hora.
   - Orçamento planejado reservado preventivamente pelo `CostManager`.

5. **Invalidação por Alteração Material e Recusa no Servidor** (M04-A05):
   - Qualquer alteração posterior à aprovação (adição/remoção de slide, troca de motor, alteração de prompt ou modelo) dispara `_on_material_change`.
   - A aprovação anterior é imediatamente invalidada no banco (`is_valid = 0` com motivo da invalidação registrado).
   - O status da campanha reverte para `draft`, a versão do plano é incrementada e o vínculo aprovado é limpo.
   - Tentativa de enfileirar (`queue_execution`) sem aprovação válida para a versão corrente é estritamente RECUSADA no servidor com `UnapprovedExecutionError`.


