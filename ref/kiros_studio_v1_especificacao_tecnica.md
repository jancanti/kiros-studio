# KIROS Studio V1
## Especificação Técnica, Produto e Prompt Mestre de Implementação

**Status:** aprovado para implementação da V1

**Objetivo:** construir uma primeira versão enxuta, funcional e robusta do KIROS Studio, mantendo foco em estratégia de crescimento, criação de campanhas, geração visual, organização de conteúdo, publicação controlada e aprendizado.

---

# 1. Visão do produto

O KIROS Studio é um estúdio inteligente de estratégia, criação e operação de conteúdo para a KIROS Aromas.

O sistema deve funcionar como um **Creative Director central**, responsável por interpretar objetivos, contexto da marca, produtos, referências, dados e histórico para propor e executar campanhas.

Os modelos de IA são ferramentas especializadas. Eles não devem funcionar como cérebros estratégicos independentes.

## Princípios

1. Estratégia antes da geração.
2. Aprovação antes de ações caras.
3. Economia de tokens e créditos.
4. Fidelidade máxima aos produtos reais.
5. Design gráfico determinístico sempre que possível.
6. Memória contextual, compacta e relevante.
7. Automação com controle humano.
8. Dados comerciais nunca podem ser inventados.
9. Histórico e versões devem ser preservados.
10. A V1 deve permanecer enxuta.

---

# 2. Escopo fechado da V1

A V1 deve contemplar:

- Creative Director.
- Estratégia de crescimento.
- Pilares de conteúdo.
- Banco de ideias.
- Campanhas.
- Briefing híbrido.
- Storyboard.
- Brand Bible.
- Product Bible.
- Biblioteca de referências visuais.
- Geração de imagens.
- Pipelines multimodelo.
- Seleção de engine.
- Controle de custo.
- Economia de tokens.
- Product Fidelity Check.
- Layout Engine.
- Editor visual semântico.
- Copy e legendas.
- Stories.
- Diversidade visual.
- Controle de repetição.
- Seleção de produtos.
- Calendário editorial.
- Integração operacional com Instagram.
- Auditoria pré-publicação.
- Aprovação.
- Histórico e versões.
- Biblioteca de prompts.
- Aprendizado controlado.
- Memória contextual.
- Command Bar.
- Busca global.
- Dashboard.
- Biblioteca de ativos.
- Arquitetura local-first.
- Banco de dados enxuto.
- Testes de providers.

**Não implementar funcionalidades fora deste escopo nesta fase.**

**Não criar V1.5, V2 ou roadmap de funcionalidades.**

---

# 3. Contexto da KIROS

## Marca

**Nome:** KIROS Aromas

**Instagram:** @kiros.sp

**E-mail:** oi@usekiros.com.br

**Região:** Sorocaba-SP

## Posicionamento

A KIROS trabalha com aromas e produtos artesanais para casa, buscando uma percepção de luxo acessível.

Personalidade:

- elegante;
- divertida;
- acolhedora;
- contemporânea;
- humana;
- natural.

Direção estética:

**antigo chique e novo moderno**

Referências conceituais:

- mitologia grega;
- luxo editorial;
- interiores sofisticados;
- estética mediterrânea;
- arquitetura contemporânea brasileira.

Referências de posicionamento visual:

- Cire Trudon;
- Diptyque;
- Jo Malone;
- Voluspa.

Essas marcas são apenas referências de posicionamento. Não copiar identidade, layouts, imagens ou campanhas.

---

# 4. Direção visual

Priorizar:

- arquitetura contemporânea brasileira;
- arquitetura mediterrânea;
- madeira;
- linho;
- pedra;
- travertino;
- cerâmica;
- vidro;
- plantas;
- tons neutros;
- iluminação lateral natural;
- fotografia editorial;
- profundidade de campo realista;
- aparência de fotografia profissional;
- sensação de fotografia feita com câmera ou smartphone premium;
- composição sofisticada, porém natural.

Evitar:

- aparência de banco de imagens;
- renders artificiais;
- CGI evidente;
- excesso de dourado;
- neon;
- cores excessivamente saturadas;
- ambientes genéricos;
- excesso de objetos;
- composição artificial;
- alterações no produto real.

---

# 5. Arquitetura geral

A arquitetura deve ser modular e desacoplada.

```text
UI
↓
Application / API
↓
Creative Director
↓
Domain Services
↓
Providers / Engines
↓
Infrastructure
```

O Creative Director não pode depender diretamente de um provider específico.

A aplicação deve conseguir substituir um provider sem reescrever o núcleo estratégico.

---

# 6. Abstrações obrigatórias

Criar interfaces/abstrações para:

```text
LLMProvider
ImageEngine
ImagePipelineEngine
StorageProvider
DatabaseProvider
SocialPublisher
ProductDataProvider
InventoryProvider
SalesProvider
AnalyticsProvider
```

---

# 7. Image Engines

A V1 deve possuir arquitetura para:

```text
GeminiImageEngine
OpenAIImageEngine
FireflyImageEngine
```

Também deve existir uma interface que permita:

```text
CustomImageProvider
```

Os IDs exatos dos modelos devem ser validados contra a documentação oficial vigente durante a implementação.

**Não hardcodar IDs presumidos ou modelos inexistentes.**

---

# 8. Tela de configuração e teste de providers

Criar uma tela específica para providers.

O usuário deve conseguir:

- adicionar provider;
- selecionar tipo;
- inserir configuração;
- configurar modelo;
- testar conexão;
- executar teste simples;
- visualizar sucesso;
- visualizar erro;
- visualizar latência;
- ativar/desativar provider.

Credenciais:

- nunca devem aparecer no frontend depois de salvas;
- nunca devem ser incluídas em logs;
- devem ser armazenadas de forma segura.

---

# 9. Creative Director

Criar um serviço central:

```text
CreativeDirector
```

Responsabilidades:

- interpretar briefing;
- entender objetivo;
- consultar contexto relevante;
- analisar Brand Bible;
- analisar Product Bible;
- considerar dados;
- selecionar produtos;
- propor estratégia;
- construir campanha;
- criar storyboard;
- recomendar engine;
- montar pipeline;
- estimar custo;
- solicitar aprovação;
- supervisionar execução;
- validar resultados;
- registrar decisões;
- aprender com correções.

O Creative Director é o cérebro estratégico.

Os modelos de IA são ferramentas.

Não transformar cada pequena operação em uma chamada independente de LLM.

---

# 10. Fluxo principal de campanha

```text
Ideia
↓
Briefing
↓
Confirmação
↓
Estratégia
↓
Seleção de produto
↓
Storyboard
↓
Escolha de engine
↓
Pipeline
↓
Estimativa de custo
↓
Aprovação
↓
Fila
↓
Execução
↓
Product Fidelity Check
↓
Layout
↓
Copy
↓
Auditoria
↓
Aprovação final
↓
Publicação / agendamento
↓
Medição
↓
Aprendizado
```

---

# 11. Briefing híbrido

O usuário pode começar com linguagem livre.

Exemplo:

> Quero uma campanha para mostrar minhas velas em ambientes sofisticados.

O sistema deve interpretar a intenção e converter progressivamente a ideia em dados estruturados.

Não fazer um questionário excessivamente longo.

Perguntar somente informações necessárias.

Quando várias informações forem necessárias, agrupá-las de maneira lógica.

---

# 12. Objetivos de campanha

Suportar:

- vendas;
- lançamento;
- awareness;
- engajamento;
- relacionamento;
- educação;
- tráfego;
- sazonal;
- personalizado.

O usuário pode definir o objetivo.

O Creative Director também pode recomendar:

- objetivo principal;
- objetivo secundário;
- justificativa;
- nível de confiança.

---

# 13. Estratégia de crescimento

O sistema deve trabalhar com:

```text
Descoberta
↓
Interesse
↓
Relacionamento
↓
Visita ao perfil
↓
Conversão
```

Métricas principais:

- alcance de não seguidores;
- visualizações;
- crescimento de seguidores;
- visitas ao perfil;
- compartilhamentos;
- salvamentos;
- comentários;
- ações no site;
- conversões quando disponíveis.

Conteúdo de descoberta pode ser adjacente à categoria da KIROS, desde que exista uma ponte clara com a marca.

Para cada sugestão adjacente, explicar:

- por que pode atrair o público;
- qual é a relação com KIROS;
- como criar a ponte.

---

# 14. Pilares de conteúdo

Pilares iniciais:

1. Produtos
2. Lifestyle
3. Marca
4. Educativo
5. Relacionamento
6. Comercial

Cada pilar possui:

- peso;
- frequência;
- histórico;
- saturação;
- desempenho.

Alterações estruturais exigem aprovação.

Quando surgir um tema fora dos pilares:

```text
Outro
```

O sistema pode propor um novo pilar permanente, mas não criá-lo oficialmente sem aprovação.

---

# 15. Datas sazonais

Prioridades:

- Natal;
- Dia das Mães.

Começar planejamento aproximadamente 2–3 meses antes.

Fases:

1. Warm-up.
2. Consideração.
3. Conversão.
4. Last Call.

Outras datas podem ser ativadas/desativadas.

Datas prioritárias podem gerar rascunhos antecipados, mas não entram no calendário oficial sem aprovação.

---

# 16. Banco de ideias

Limite:

```text
5 ideias por pilar
```

Com seis pilares:

```text
máximo de 30 ideias ativas
```

Estados:

```text
suggested
approved
rejected
scheduled
published
archived
pinned
```

Quando uma ideia for rejeitada:

- arquivar;
- registrar motivo;
- não reapresentar a mesma ideia com alteração superficial;
- considerar o motivo em futuras sugestões;
- propor substituta quando necessário.

O usuário pode fixar ou bloquear ideias.

---

# 17. Seleção de produtos

Modo:

- manual;
- automático.

A seleção automática pode considerar:

- vendas;
- estoque;
- lançamentos;
- sazonalidade;
- exposição recente;
- desempenho histórico;
- relação com conceito;
- diversidade do catálogo.

Na V1:

- produtos e estoque podem ser administrados manualmente;
- vendas podem ser importadas por CSV.

**O Creative Director nunca pode inventar dados comerciais.**

---

# 18. Brand Bible

Criar uma Brand Bible global e overrides por campanha.

Conteúdo:

- logo;
- variantes;
- fontes;
- cores;
- estilo fotográfico;
- arquitetura;
- decoração;
- materiais;
- paleta;
- composição;
- avoid-list;
- referências aprovadas;
- informações da marca.

Overrides de campanha não alteram a Brand Bible global.

A versão oficial é protegida e somente pode evoluir mediante aprovação.

---

# 19. Product Bible

Cada produto deve possuir uma ficha visual detalhada.

O usuário fornece aproximadamente:

```text
3–5 fotografias por produto
```

O sistema utiliza visão computacional para analisar:

- formato;
- proporção;
- material;
- vidro;
- tampa;
- etiqueta;
- logo;
- cores;
- embalagem.

Cada atributo recebe:

```text
free
protected
critical
```

## Free

Pode variar em contexto.

## Protected

Exige alerta e confirmação antes de alteração.

## Critical

Não pode ser alterado por padrão.

Product Bible deve ser versionada.

Nenhuma alteração oficial sem aprovação.

---

# 20. Product Reference Set

Para cada produto:

- armazenar referências;
- classificar ângulos;
- identificar melhor imagem;
- criar Reference Set;
- permitir seleção automática;
- permitir override manual.

As referências devem ser escolhidas de acordo com a tarefa.

---

# 21. Visual Reference Library

Biblioteca permanente e temporária.

Tipos:

```text
permanent
campaign
```

Analisar:

- iluminação;
- composição;
- materiais;
- paleta;
- arquitetura;
- enquadramento;
- atmosfera;
- distância da câmera;
- estilo fotográfico.

Classificar origem:

```text
own
licensed
public_domain
external
unknown
```

Quando direitos comerciais forem desconhecidos:

```text
inspiration_only
```

Referências externas são inspiração, não material para reprodução direta.

"Descaracterizar" uma referência pode reduzir risco de cópia, mas não constitui garantia jurídica.

---

# 22. Image Engine Router

Por campanha:

- engine padrão;
- engine por slide;
- recomendação automática.

A recomendação deve mostrar:

```text
Provider
Model
Reason
Estimated cost
Confidence
Alternatives
```

O usuário pode alterar manualmente.

---

# 23. Multi-engine pipeline

Permitir composição de engines dentro de uma mesma campanha.

Exemplo:

```text
Environment
↓
Product Integration
↓
Harmonization
↓
Layout
```

Porém:

**usar o menor número de etapas necessário para atingir a qualidade desejada.**

Mais etapas podem aumentar:

- custo;
- latência;
- risco de degradação;
- complexidade.

---

# 24. Cost Manager

Criar:

```text
CostManager
```

Registrar:

- provider;
- modelo;
- estimativa;
- custo real;
- quantidade de gerações;
- etapas;
- campanha;
- asset;
- timestamp.

Antes de ações caras:

```text
Plano
Custo
Impacto
Confiança
Alternativas
Aprovação
```

---

# 25. Economia de tokens

Princípio obrigatório:

**Não triturar tokens antes da aprovação de ações relevantes.**

Implementar:

- contexto mínimo;
- resumo compacto;
- estado estruturado;
- recuperação seletiva da Brand Bible;
- recuperação seletiva da Product Bible;
- RAG somente quando necessário;
- cache;
- modelos menores para tarefas simples;
- orçamento de contexto;
- compactação;
- proveniência;
- deduplicação.

Evitar:

- transcrições completas de LLM;
- prompts repetidos;
- contexto redundante;
- chamadas desnecessárias;
- análises duplicadas.

---

# 26. Budget

Cada campanha pode possuir:

- orçamento;
- limite;
- alertas;
- aprovação acima do limite;
- execução automática dentro do orçamento;
- custo estimado;
- custo real.

Nunca ultrapassar política de orçamento sem autorização.

---

# 27. Product Fidelity Check

Criar:

```text
ProductFidelityService
```

Resultado:

```text
Fidelidade: 94/100
```

Verificar:

- forma;
- proporção;
- tampa;
- etiqueta;
- logo;
- cores;
- material;
- atributos críticos.

Configurações:

```text
warn_only
auto_regenerate
recommend_before_spend
```

Padrão:

```text
recommend_before_spend
```

Quando falhar:

```text
Explicar problema
↓
Sugerir correção
↓
Estimar custo
↓
Solicitar aprovação
```

O score é uma estimativa de visão computacional, não uma prova absoluta.

---

# 28. Layout Engine

O Layout Engine é responsável pelo design gráfico.

Separação:

```text
Creative Director = estratégia
Image Engine = imagem
Layout Engine = design
```

Não delegar ao gerador de imagem:

- texto exato;
- logo;
- tipografia;
- posicionamento final.

Formatos:

- 4:5;
- 9:16.

Elementos semânticos:

- headline;
- image;
- logo;
- CTA;
- decorative.

---

# 29. Editor visual semântico

## Verde

Livre:

- posição;
- escala;
- enquadramento;
- iluminação.

## Amarelo

Protected:

- alerta;
- confirmação.

## Vermelho

Critical:

- bloquear;
- unlock explícito;
- registrar exceção.

Nunca alterar Product Bible automaticamente.

---

# 30. Templates

Biblioteca com:

- templates aprovados;
- famílias de layout;
- regras de composição.

Estados:

```text
active
archived
experimental
```

O Creative Director pode:

- escolher;
- adaptar;
- propor nova composição;
- salvar composição aprovada como template.

Templates experimentais exigem autorização.

Detectar sobreuso.

---

# 31. Pipeline editing

Permitir:

- visualizar resumo completo;
- expandir etapa;
- editar etapa;
- aprovar tudo;
- aprovar individualmente.

Alterações localizadas preservam o restante do pipeline.

---

# 32. Diversidade visual

Evitar repetição excessiva em:

- ambientes;
- arquitetura;
- materiais;
- paletas;
- enquadramentos;
- distância da câmera;
- ângulos;
- iluminação;
- composição;
- layouts;
- produtos;
- decoração;
- estilo fotográfico.

A diversidade deve ser estratégica.

---

# 33. Saturação

Criar mapa de saturação considerando:

- produto;
- fragrância;
- tema;
- pilar;
- formato;
- CTA;
- campanha;
- frequência;
- recência.

Alertar sobre saturação.

Não impedir repetição intencional.

---

# 34. Copy e voz

A voz da KIROS deve ser:

- humana;
- leve;
- relaxada;
- natural;
- brasileira;
- elegante sem rigidez;
- divertida quando apropriado.

Evitar:

- clichês de IA;
- estruturas formulaicas;
- excesso de adjetivos;
- linguagem corporativa;
- CTAs previsíveis;
- texto artificial.

Não usar hashtags automaticamente.

Não usar emojis em:

- legendas;
- CTAs;
- textos editoriais.

---

# 35. Legendas

Modos:

```text
automatic
suggestions
user_provided
ai_plus_user
```

Nunca inventar:

- preço;
- estoque;
- disponibilidade;
- promoção;
- condição comercial.

SEO deve ocorrer naturalmente com termos ligados a:

- produto;
- fragrância;
- categoria;
- ocasião;
- intenção de compra;
- localização;
- datas sazonais;
- casa;
- decoração;
- presentes;
- aromatização.

---

# 36. CTA

CTA não é obrigatório.

Usar somente quando o Creative Director identificar necessidade.

Pode ser:

- automático;
- manual;
- baseado em intenção;
- sugestão.

Não usar fórmulas artificiais como pedir comentários sem motivo.

---

# 37. Preço e site

Não mostrar preço por padrão.

Se mostrar preço for estrategicamente melhor:

1. explicar;
2. solicitar aprovação.

Nunca inventar preço.

Priorizar link da bio.

Durante configuração inicial, solicitar URL do site ou página de destino.

Na V1, não implementar integração profunda com website.

---

# 38. Stories

Stories são conteúdo próprio.

Podem ser:

```text
independent
derived_from_campaign
```

Não simplesmente redimensionar feed.

Permitir planejamento de sequência.

Usar interações somente quando fizer sentido.

---

# 39. Calendário editorial

Criar calendário inteligente com:

- visão calendário;
- campanhas;
- conteúdo;
- pilares;
- datas;
- recomendações.

Considerar:

- frequência;
- diversidade;
- saturação;
- prioridades;
- histórico.

---

# 40. Frequência

O usuário define limites e preferências.

O Creative Director otimiza dentro das restrições.

Se identificar necessidade de alteração:

- explicar;
- justificar;
- recomendar;
- solicitar aprovação quando necessário.

---

# 41. Instagram

Após uma campanha estar totalmente aprovada:

1. analisar dados disponíveis;
2. recomendar melhor dia/horário;
3. explicar base;
4. permitir alteração manual.

Manual sempre vence.

Registrar:

```text
recommended_time
selected_time
accepted
data_basis
later_performance
```

---

# 42. Dados escassos

Usar camadas:

```text
KIROS
↓
Setor
↓
Plataforma geral
```

Mostrar:

- fonte;
- camada;
- confiança.

Nunca apresentar estimativa como certeza.

---

# 43. Análise competitiva

Permitir análise de:

- concorrentes informados;
- descoberta por categoria/localização;
- marcas premium;
- perfis relevantes;
- tendências;
- decoração;
- arquitetura;
- lifestyle;
- fotografia.

Objetivos:

- tendências;
- oportunidades;
- saturação;
- diferenciação.

Nunca copiar.

Registrar data da análise.

---

# 44. Tendências

Para cada tendência:

```text
Trend
Relevance
Saturation
Copy Risk
KIROS Interpretation
Potential
Confidence
Recommendation
```

---

# 45. Experimentos

Classificar:

```text
Low Risk
Medium Risk
High Risk
```

Baixo risco:

- pode executar conforme autorização.

Médio:

- solicitar aprovação.

Alto:

- sempre aguardar aprovação.

---

# 46. A/B

Permitir testes de:

- imagem;
- composição;
- copy;
- CTA;
- enquadramento;
- produto;
- variável relevante.

Registrar:

- hipótese;
- controle;
- variável;
- resultado;
- amostra;
- confiança.

Evitar conclusões fortes com amostras pequenas.

---

# 47. Aprendizado

Começar com recomendações.

Adaptações fortes somente com evidência suficiente e aprovação.

Fluxo:

```text
Correção de campanha
→ aprendizado local

Preferência repetida
→ sugestão de preferência

Conflito
→ alerta

Nova regra
→ proposta de Brand Bible

Mudança de produto
→ proposta de Product Bible
```

Nenhuma alteração permanente automática.

---

# 48. Memória

Tipos:

```text
campaign_context
recurring_preference
brand_rule
commercial_data
creative_decision
operational_setting
```

Cada memória relevante deve possuir proveniência.

Não carregar toda memória em toda chamada.

---

# 49. Conflitos

Quando houver conflito:

```text
Detectar
↓
Mostrar informações divergentes
↓
Mostrar origem
↓
Avaliar confiabilidade
↓
Recomendar
↓
Perguntar ao usuário se impacto alto
↓
Registrar decisão
```

Nunca sobrescrever automaticamente informação oficial.

---

# 50. Monitoramento da geração

Modos:

```text
Quick
Supervised
Detailed
Manual
```

---

# 51. Intervenção localizada

Permitir:

- alterar slide;
- alterar asset;
- regenerar somente afetado;
- preservar restante.

---

# 52. Cancelamento e pausa

Permitir:

- cancelar geração atual;
- cancelar slide;
- cancelar campanha;
- pausar;
- retomar.

Preservar tudo já concluído.

Mostrar custo e risco de cobrança.

Nunca apagar versões automaticamente.

---

# 53. Versionamento

Registrar:

- versão;
- motivo;
- solicitante;
- engine;
- prompt;
- referências;
- custo;
- fidelidade;
- timestamp.

Permitir:

- comparar;
- restaurar;
- usar como base.

---

# 54. Comparação visual

Permitir até 3 versões lado a lado.

Mostrar:

- imagem;
- engine;
- modelo;
- custo;
- fidelidade;
- diferenças.

Ações:

```text
choose
use_as_base
record_learning
```

---

# 55. Prompt Library

O sistema pode sugerir prompts que apresentaram bons resultados.

Somente salvar permanentemente após aprovação.

Registrar:

- objetivo;
- engine;
- contexto;
- resultado;
- desempenho;
- aprovação.

---

# 56. Approval System

Cada campanha define:

```text
minimal
step_by_step
full_control
```

Ações caras seguem política de aprovação.

Publicação exige confirmação explícita.

Ações irreversíveis exigem confirmação.

Comandos ambíguos nunca equivalem a autorização.

---

# 57. Command Bar

Criar Command Bar com linguagem natural.

Exemplos:

```text
Abra a última campanha.
Mostre minhas ideias de Lifestyle.
Quanto esta campanha vai custar?
Compare as três últimas versões.
Pause a geração.
```

Ações simples e reversíveis podem executar diretamente.

Ações que consomem créditos devem mostrar impacto.

Publicação exige confirmação.

---

# 58. Busca global

Busca:

- natural;
- semântica;
- case-insensitive;
- accent-insensitive.

Pesquisar:

- campanhas;
- produtos;
- imagens;
- versões;
- ideias;
- templates;
- decisões;
- histórico.

Usar filtros.

Preservar o texto original.

---

# 59. Dashboard

Dashboard contextual:

```text
Hoje
Oportunidade
Próximo passo recomendado
Calendário
Criação
Aprendizados
```

---

# 60. Navegação

```text
Início
Criar
Calendário
Conteúdo
Biblioteca
Insights
Marca
Configurações
```

---

# 61. Biblioteca

Organizar:

- produtos;
- referências;
- imagens;
- campanhas;
- templates;
- prompts;
- versões.

Permitir busca e filtros.

---

# 62. Arquitetura local-first

A V1 deve priorizar arquitetura local-first.

Sugestão:

- aplicação web local;
- SQLite;
- filesystem para imagens e arquivos;
- camada de providers;
- serviços desacoplados;
- fila de execução.

Imagens e arquivos não devem ser blobs dentro do SQLite.

---

# 63. Banco de dados

SQLite deve armazenar:

- IDs;
- relacionamentos;
- metadados essenciais;
- estados;
- custos;
- versões;
- proveniência.

Evitar:

- transcrições completas de LLM;
- logs gigantes;
- prompts duplicados;
- eventos de baixo valor.

---

# 64. Entidades principais

Criar entidades equivalentes a:

```text
BrandBible
BrandBibleVersion
Product
ProductReference
ProductBible
ProductBibleVersion
VisualReference
Campaign
CampaignBrief
CampaignPlan
Storyboard
Slide
Pipeline
PipelineStage
Asset
AssetVersion
Caption
Story
ContentPillar
Idea
Template
Prompt
Provider
Model
CostRecord
FidelityCheck
Approval
Decision
Learning
EditorialCalendarItem
SalesImport
InventoryRecord
AnalyticsSnapshot
```

---

# 65. Proveniência

Toda informação importante deve responder:

> De onde veio essa informação?

Origens possíveis:

```text
user
brand_bible
product_bible
campaign
csv
instagram
benchmark
provider
model
automatic_analysis
```

---

# 66. Estados de execução

Usar estados claros:

```text
draft
awaiting_approval
approved
queued
running
validating
completed
failed
paused
cancelled
archived
```

---

# 67. Filas e concorrência

Controlar:

- concorrência;
- rate limits;
- retries;
- timeout;
- cancelamento;
- pausa;
- prioridade.

Retries não podem gerar custos inesperados.

---

# 68. Idempotência

Operações importantes devem ser idempotentes.

Evitar:

- publicação duplicada;
- geração duplicada;
- registros duplicados;
- cobrança duplicada.

---

# 69. Falhas

Quando ocorrer falha:

```text
Identificar provider
↓
Identificar etapa
↓
Mostrar causa provável
↓
Sugerir correção
↓
Mostrar custo potencial
↓
Retry conforme política
```

Nunca executar retry infinito.

---

# 70. Segurança

Proteger:

- API keys;
- tokens;
- credenciais;
- dados comerciais;
- arquivos.

Nunca enviar credenciais ao frontend.

Nunca registrar credenciais em logs.

---

# 71. Backup

Fazer backup de:

- SQLite;
- Brand Bible;
- Product Bible;
- campanhas;
- assets;
- configurações importantes.

Não apagar histórico automaticamente.

---

# 72. API interna

Criar camada entre UI, Creative Director, serviços, providers, banco e filesystem.

Exemplos:

```text
campaign.create
campaign.plan
campaign.approve
campaign.execute
campaign.cancel
campaign.pause
campaign.resume

asset.generate
asset.validate
asset.compare

provider.test
provider.list

product.create
product.analyze

brand.get
brand.update

calendar.recommend

insights.analyze
```

Os nomes podem ser adaptados à stack.

A separação de responsabilidades deve permanecer.

---

# 73. Estrutura sugerida

```text
kiros-studio/
├── app/
│   ├── ui/
│   ├── api/
│   └── commands/
│
├── core/
│   ├── creative-director/
│   ├── campaigns/
│   ├── products/
│   ├── brand/
│   ├── content/
│   ├── calendar/
│   ├── insights/
│   ├── approvals/
│   ├── learning/
│   └── memory/
│
├── engines/
│   ├── image/
│   │   ├── gemini/
│   │   ├── openai/
│   │   └── firefly/
│   ├── layout/
│   └── fidelity/
│
├── providers/
│   ├── llm/
│   ├── image/
│   ├── storage/
│   ├── database/
│   ├── social/
│   └── analytics/
│
├── infrastructure/
│   ├── sqlite/
│   ├── filesystem/
│   ├── queue/
│   ├── security/
│   └── logging/
│
├── assets/
├── tests/
└── docs/
```

A stack pode adaptar essa estrutura, mas não deve quebrar os limites arquiteturais.

---

# 74. UX

A interface deve ser:

- limpa;
- premium;
- funcional;
- simples;
- rápida;
- orientada a decisões.

Evitar dashboards excessivamente complexos.

O usuário deve sempre conseguir entender:

```text
O que o Studio recomenda?
Por quê?
Quanto custa?
O que acontecerá se eu aprovar?
```

---

# 75. Tela de aprovação

Antes de uma geração relevante, apresentar algo equivalente a:

```text
CAMPANHA

Objetivo:
...

Conceito:
...

Produtos:
...

Storyboard:
...

Engine:
...

Pipeline:
...

Gerações estimadas:
...

Custo estimado:
...

Confiança:
...

[Editar]
[Cancelar]
[Aprovar execução]
```

---

# 76. Regra de tarefas determinísticas

Se uma tarefa puder ser resolvida sem LLM, resolver sem LLM.

Exemplos:

- cálculos;
- estados;
- filtros;
- ordenação;
- versionamento;
- comparação de metadados;
- orçamento;
- regras de aprovação;
- validação de formato.

---

# 77. Regra de contexto

Antes de cada chamada de LLM:

1. determinar a informação necessária;
2. recuperar somente essa informação;
3. compactar;
4. eliminar redundância;
5. executar.

Nunca enviar toda a base de conhecimento por padrão.

---

# 78. Regra de produto

Quando houver imagens reais do produto:

- utilizá-las como referência;
- preservar identidade;
- não substituir por produto genérico.

Se a fidelidade estiver abaixo do limite:

```text
alertar
↓
explicar
↓
propor correção
↓
estimar custo
```

---

# 79. Regra de publicação

Publicação é ação relevante.

Nunca publicar com comando ambíguo.

Exigir confirmação explícita.

---

# 80. Regra de histórico

Nunca apagar automaticamente:

- campanhas;
- assets;
- versões;
- decisões;
- aprendizados;
- Brand Bible;
- Product Bible.

---

# 81. Critérios de aceitação

A V1 deve permitir:

## Marca

- configurar Brand Bible;
- versionar;
- proteger regras;
- aprovar alterações.

## Produtos

- cadastrar;
- adicionar imagens;
- analisar;
- criar Product Bible;
- classificar atributos;
- versionar.

## Referências

- adicionar;
- analisar;
- classificar;
- utilizar em campanhas.

## Providers

- cadastrar;
- testar;
- ativar;
- desativar;
- escolher modelo.

## Campanhas

- criar;
- planejar;
- selecionar objetivo;
- selecionar produtos;
- gerar storyboard;
- configurar pipeline;
- estimar custo;
- aprovar;
- executar.

## Imagens

- gerar;
- utilizar referências;
- selecionar engine;
- combinar engines;
- validar fidelidade;
- regenerar somente necessário.

## Layout

- aplicar template;
- montar composição;
- inserir texto;
- inserir logo;
- editar;
- proteger atributos.

## Conteúdo

- criar legenda;
- criar Stories;
- controlar CTA;
- respeitar voz.

## Calendário

- visualizar;
- organizar;
- recomendar horários;
- registrar decisão.

## Histórico

- versionar;
- comparar;
- restaurar;
- registrar custo;
- registrar engine;
- registrar decisão.

## Inteligência

- recomendar;
- detectar saturação;
- analisar tendências;
- aprender com correções;
- manter memória contextual.

---

# 82. Testes obrigatórios

Criar testes automatizados para:

## Estratégia

- criação de campanha;
- objetivo;
- pilares;
- seleção de produto;
- conflitos.

## Providers

- conexão;
- erro;
- timeout;
- credencial inválida;
- provider indisponível.

## Geração

- fila;
- concorrência;
- retry;
- cancelamento;
- pausa;
- retomada.

## Fidelidade

- produto correto;
- produto alterado;
- etiqueta alterada;
- logo alterado;
- threshold.

## Custos

- estimativa;
- orçamento;
- aprovação;
- limite;
- custo real.

## Layout

- 4:5;
- 9:16;
- tipografia;
- logo;
- elementos semânticos;
- proteção.

## Memória

- recuperação;
- compactação;
- relevância;
- proveniência.

## Versionamento

- criação;
- comparação;
- restauração;
- preservação.

---

# 83. Processo de implementação

Antes de escrever grande quantidade de código:

1. analisar esta especificação;
2. identificar ambiguidades reais;
3. escolher uma stack adequada;
4. criar arquitetura;
5. criar schema SQLite;
6. criar interfaces;
7. criar serviços principais;
8. criar UI;
9. integrar providers;
10. criar fila;
11. criar geração;
12. criar validação;
13. criar histórico;
14. criar testes;
15. executar testes;
16. corrigir erros;
17. validar fluxo completo.

Não interromper o desenvolvimento por detalhes que possam ser resolvidos com uma decisão técnica razoável.

Quando uma decisão técnica for necessária, priorizar:

- simplicidade;
- modularidade;
- baixo custo;
- facilidade de manutenção;
- substituição de providers.

---

# 84. Definition of Done

A V1 somente deve ser considerada concluída quando:

1. projeto inicia corretamente;
2. interface funciona;
3. SQLite funciona;
4. filesystem funciona;
5. providers podem ser configurados;
6. providers podem ser testados;
7. produtos podem ser cadastrados;
8. Brand Bible funciona;
9. Product Bible funciona;
10. campanhas podem ser criadas;
11. storyboard pode ser criado;
12. pipeline pode ser configurado;
13. custo pode ser estimado;
14. aprovação funciona;
15. geração funciona;
16. Fidelity Check funciona;
17. Layout Engine funciona;
18. copy funciona;
19. versões funcionam;
20. comparação funciona;
21. cancelamento funciona;
22. pausa funciona;
23. retomada funciona;
24. calendário funciona;
25. busca funciona;
26. memória funciona;
27. testes automatizados passam;
28. nenhum erro crítico conhecido permanece.

---

# 85. Regras finais para a Antigravity CLI

Estas regras são obrigatórias.

1. Não adicionar funcionalidades fora desta especificação.
2. Não criar roadmap.
3. Não criar V1.5.
4. Não criar V2.
5. Não transformar o projeto em arquitetura excessivamente complexa.
6. Não transformar cada ação em uma chamada de LLM.
7. Não gastar créditos antes da aprovação necessária.
8. Não inventar informações comerciais.
9. Não alterar produtos reais sem validação.
10. Não delegar tipografia e texto exato ao gerador quando o Layout Engine puder resolver.
11. Não alterar Brand Bible oficial sem aprovação.
12. Não alterar Product Bible oficial sem aprovação.
13. Não apagar histórico.
14. Não carregar contexto desnecessário.
15. Não hardcodar modelos sem validar documentação atual.
16. Providers devem ser substituíveis.
17. Engines devem ser substituíveis.
18. Creative Director não deve depender diretamente de provider.
19. Ações caras devem possuir estimativa.
20. Decisões importantes devem possuir proveniência.

---

# 86. Prompt mestre de execução

Após analisar todo este documento, construa o KIROS Studio V1.

Não entregue somente mockups.

Construa uma aplicação funcional.

Priorize:

```text
Arquitetura sólida
+
V1 enxuta
+
Creative Director
+
Brand Bible
+
Product Bible
+
Image Engines
+
Cost Control
+
Token Economy
+
Product Fidelity
+
Layout Engine
+
Campaign Workflow
+
Approval System
+
Versioning
+
Learning
+
Memory
```

Antes de implementar cada módulo:

1. verificar sua relação com esta especificação;
2. evitar funcionalidades desnecessárias;
3. preferir solução determinística quando possível;
4. minimizar chamadas de LLM;
5. preservar modularidade;
6. preservar controle de custo;
7. preservar aprovação humana.

Se uma funcionalidade não estiver prevista nesta especificação, não implementar.

O resultado deve ser uma V1 funcional, modular, econômica e pronta para uso real pela KIROS.
