---
name: KIROS Studio Design System
description: Sistema visual contemporâneo, editorial e arquitetural inspirado no Copy.ai para o KIROS Studio V1
colors:
  primary: "#693edf"
  primary-dark: "#3b0d96"
  primary-deeper: "#29007a"
  primary-mid: "#4514a6"
  primary-light: "#4f1bb7"
  ink: "#171717"
  ink-soft: "#222222"
  ink-graphite: "#364045"
  muted-blue: "#566b76"
  muted: "#5d5d5d"
  nav-link: "#333333"
  canvas: "#ffffff"
  surface-input: "#f6fafb"
  hairline: "#e0e0e0"
  hairline-soft: "#ccd9e0"
  hairline-cool: "#e4edf1"
typography:
  display:
    fontFamily: "'Geist', system-ui, -apple-system, sans-serif"
    fontSize: "clamp(36px, 5.5vw, 68px)"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-1.2px"
  headline:
    fontFamily: "'Geist', system-ui, -apple-system, sans-serif"
    fontSize: "23px"
    fontWeight: 600
    lineHeight: 1.35
  title:
    fontFamily: "'Geist', system-ui, -apple-system, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "22px"
  label:
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    letterSpacing: "1px"
rounded:
  none: "0px"
  sm: "4px"
  md: "8px"
  circle: "50%"
spacing:
  xs: "6px"
  sm: "10px"
  base: "16px"
  md: "20px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.canvas}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "12px 16px"
    height: "47px"
  button-primary-hover:
    backgroundColor: "{colors.primary-dark}"
  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "12px 16px"
    height: "47px"
  text-input:
    backgroundColor: "{colors.surface-input}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "0 18px"
    height: "42px"
  feature-card:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "20px 24px"
  testimonial-card:
    backgroundColor: "{colors.ink-soft}"
    textColor: "{colors.canvas}"
    rounded: "{rounded.sm}"
    padding: "24px"
  gradient-panel:
    backgroundColor: "{colors.primary-dark}"
    textColor: "{colors.canvas}"
    rounded: "{rounded.sm}"
    padding: "32px"
---

# Design System: KIROS Studio

## Overview

**Creative North Star: "The Olfactory Atelier"**

O KIROS Studio expressa a fusão entre a precisão arquitetural contemporânea e a calma sensorial botânica de um ateliê de alta perfumaria. Sua linguagem visual herda a disciplina editorial suíça: espaços em branco generosos, hierarquia tipográfica calibrada em dois patamares rígidos e o uso comedido de um roxo elétrico (`#693edf`) mantido em estrita reserva.

Em vez de gradientes difusos genéricos ou sombras flutuantes que poluem a tela, o estúdio utiliza superfícies planas delimitadas por linhas milimétricas (`#e0e0e0`) e grandes lajes geométricas em gradiente (*Architectural Gradient Slab*) para abrigar métricas operacionais e estados ativos. O ritmo da interface desacelera a ansiedade operacional e instiga a direção criativa de longo prazo.

**Key Characteristics:**
- **Brand Voltage em Reserva Estrita**: O roxo elétrico (`#693edf`) só aparece nas ações primárias essenciais e no ponto de fuga do gradiente arquitetural.
- **Divisão Tipográfica Bipolar**: Geist atua exclusivamente nas faixas de display e títulos editoriais (23px a 68px); Inter assume integralmente corpo, formulários, tabelas e micro-labels (12px a 16px).
- **Escala de Raios Binária (4px)**: Cantos com raio firme de 4px (`--radius-sm`) em cards, botões e painéis, ou 0px em campos de entrada, garantindo sobriedade corporativa e artesanal.
- **Profundidade por Linhas e Tonalidades**: Ausência de sombras pesadas; limites desenhados por hairlines de 1px (`#e0e0e0`, `#e4edf1`) e contrastes deliberados com fundo frio (`#f6fafb`).

## Colors

A paleta equilibra grafites densos com superfícies de papel frio e a voltagem do roxo elétrico.

### Primary
- **Electric Indigo** (`#693edf`): Ponto focal de ação, foco de formulários ativos e base inferior do gradiente.
- **Deep Indigo / Midnight Purple** (`#29007a` → `#4514a6` → `#3b0d96`): Lajes arquiteturais e estados de hover dos botões principais.

### Neutral
- **Graphite Ink** (`#171717`): Texto principal, títulos e elementos de contraste máximo.
- **Soft Dark Slate** (`#222222`): Superfície de cartões escuros de contraste (*testimonial cards*) e notas com alta autoridade.
- **Slate Graphite** (`#364045`): Elementos de interface de peso médio e metadados estruturados.
- **Muted Blue-Grey** (`#566b76`): Parágrafos corridos, textos secundários e legendas de suporte.
- **Neutral Grey** (`#5d5d5d`): Labels secundários, estados inativos e notas laterais.
- **Pure Canvas** (`#ffffff`): Fundo primário da aplicação, cards e sidebar limpa.
- **Cool Surface** (`#f6fafb`): Fundo de inputs, chips de pilar e áreas ativas de navegação.
- **Hairline Gray** (`#e0e0e0` / `#e4edf1`): Divisores de 1px e contornos de cartões.

### Named Rules
**The Reserve Voltage Rule.** O roxo elétrico (`#693edf`) nunca deve cobrir mais de 5% da superfície visual da tela. Sua força provém da sua raridade; se tudo for roxo, nada é prioridade.
**The Graphite Ladder Rule.** Nunca utilize preto puro (`#000000`) para textos ou bordas. A gradação de grafite (`#171717` para leitura principal, `#566b76` para corpo) sustenta a elegância editorial.

## Typography

**Display Font:** Geist, com fallback para ABC Normal, system-ui, sans-serif.
**Body Font:** Inter, com fallback para system-ui, -apple-system, sans-serif.

**Character:** A convivência entre Geist e Inter estabelece uma separação nítida entre o impacto editorial de revista e a precisão suíça de ferramentas de trabalho.

### Hierarchy
- **Display** (600, `clamp(36px, 5.5vw, 68px)`, line-height 1.1, letter-spacing -1.2px): Títulos de página de grande formato.
- **Headline** (600, 23px, line-height 1.35): Títulos de seções e painéis principais.
- **Title** (600, 18px, line-height 1.4): Títulos de cartões de ideias, blocos e cabeçalhos de grupos.
- **Body** (400, 14px, line-height 22px): Texto corrido, explicações e descrições conceituais (max-width de 65–75ch).
- **Label** (600, 12px, letter-spacing 1px, uppercase): Eyebrows, tags de pilar e badges de status.

### Named Rules
**The Two-Tier Separation Rule.** A família Geist nunca é utilizada abaixo de 18px, e a família Inter nunca sobe acima de 16px. A fronteira entre o título e a leitura operacional é intransponível.

## Layout

A espacialidade segue um modelo de grid fluído com ênfase em bancadas de trabalho assimétricas.

- **Largura Máxima do Conteúdo**: 1150px em `main`, centralizado com margens generosas de 6%.
- **Studio Workbench Grid**: Divisão em 2 colunas assimétricas (1.55fr para fluxo primário de ação e 1fr para radar estratégico de inteligência).
- **Dashboard Grid**: Grid de 2 colunas equilibradas (1fr 1fr) com espaçamento de 24px a 28px.
- **Responsividade**: Em telas menores que 960px ou 700px, os layouts colapsam de forma fluida para 1 coluna vertical mantendo a legibilidade integral.

## Elevation & Depth

O sistema rejeita sombras difusas ou neomórficas, operando prioritariamente sobre uma linguagem bidimensional plana.

- **Tonal Layering & Hairlines**: A profundidade visual é criada pela alternância deliberada entre o canvas branco (`#ffffff`), as superfícies frias (`#f6fafb`) e bordas sólidas de 1px (`#e0e0e0`).
- **Lajes de Gradiente**: Elementos de destaque ganham profundidade arquitetural por meio de gradientes verticais contidos em 3 paradas (`linear-gradient(180deg, #29007a 0%, #4514a6 50%, #693edf 100%)`).

### Named Rules
**The Zero-Shadow Rule.** Elementos em repouso não possuem `box-shadow`. Superfícies se distinguem por linhas de 1px e preenchimentos tonais sutis.

## Shapes

- **Raio Rígido de 4px (`--radius-sm`)**: Padrão universal para botões, cards, chips, painéis e diálogos.
- **Canto Reto de 0px (`--radius-none`)**: Aplicado a inputs de texto e áreas de edição pura, reforçando a seriedade de formulários.
- **Círculo Perfeito (`--radius-circle: 50%`)**: Reservado exclusivamente para avatares e indicadores de status pulsantes.

## Components

### Buttons
- **Shape:** Raio de 4px (`--radius-sm`). Altura padrão de 47px.
- **Primary:** Fundo `#693edf`, texto `#ffffff`, padding 12px 16px, peso 500, transição suave. Hover em `#3b0d96`.
- **Secondary:** Fundo `#ffffff`, texto `#171717`, borda 1px solid `#e0e0e0`, padding 12px 16px, altura 47px. Hover em fundo `#f6fafb`.
- **Danger:** Fundo `#8a2e1d`, texto branco, altura 47px para confirmações de arquivamento.

### Inputs / Fields
- **Style:** Fundo `#f6fafb`, altura 42px, padding `0 18px`, borda 1px solid `#e4edf1`, cantos retos de 0px.
- **Focus:** Contorno visível de 2px sólido em `#693edf` com offset de 2px.

### Cards / Containers
- **Corner Style:** 4px de raio.
- **Background:** Branco puro (`#ffffff`) sobre canvas.
- **Border:** 1px solid `#e0e0e0`.
- **Padding:** 20px a 28px.
- **Dark Variant:** Cartões em fundo `#222222` com texto branco e contraste acentuado.

### Chips & Badges
- **Chips de Pilar:** Fundo `#f6fafb`, borda `#e0e0e0`, padding 8px 12px, raio 4px.
- **Badges de Status:** Fundo suave, texto em caixa alta, fonte 11px Inter, peso 600, letter-spacing 0.5px.

### Navigation (Sidebar & Header)
- **Sidebar:** Fundo branco puro (`#ffffff`), largura fixa de 236px a 240px, borda direita sutil `#e0e0e0`.
- **Links:** Fonte Inter 14px em `#333333`. Link ativo com fundo `#f6fafb`, texto `#693edf` e indicador lateral roxo de 3px.

## Do's and Don'ts

### Do:
- **Do** manter todos os cantos em 4px, exceto inputs planos (0px).
- **Do** reservar o roxo `#693edf` estritamente para o botão de ação principal ou foco ativo.
- **Do** usar títulos em Geist com peso 600 e corpo de texto em Inter com peso 400.
- **Do** utilizar divisores sutis de 1px (`#e0e0e0`) em vez de sombras para separar seções.
- **Do** manter a altura dos botões primários em 47px e campos de texto em 42px.

### Don't:
- **Don't** aplicar `box-shadow` difuso em cards ou botões.
- **Don't** usar preto puro `#000000` em textos; use a escada de grafite (`#171717`, `#566b76`).
- **Don't** usar a fonte Geist em tamanhos de corpo menores que 18px.
- **Don't** criar paletas de botões multicoloridas aleatórias; mantenha o binômio `#693edf` (ação) e `#ffffff` com borda (secundário).
- **Don't** pintar seções inteiras com fundos roxos sólidos; use o *Architectural Gradient Slab* apenas em lajes contidas de métricas.
