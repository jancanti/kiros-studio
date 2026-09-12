# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Diretor de Criação, Operador e Fundador da marca **KIROS Aromas** (produtos aromáticos artesanais: velas, difusores e home sprays de Sorocaba · SP).
Opera o estúdio em sua rotina estratégica para conceber, planejar, gerar, revisar e aprovar campanhas de conteúdo visual e textual consistentes com a identidade da marca, sem alucinações comerciais e sem desperdício de tokens ou créditos.

## Product Purpose

Estúdio inteligente de estratégia, criação e operação de conteúdo para a KIROS Aromas.
Funciona como um **Creative Director central** que interpreta objetivos, contexto da marca, produtos e histórico para propor, produzir e gerenciar campanhas com alto padrão estético.
O sucesso significa manter uma presença de marca intencional, consistente e com economia de recursos através de automação governada pelo olhar humano.

## Positioning

"Intenção antes da criação."
O KIROS Studio não é um gerador genérico de postagens automatizadas. Ele é um sistema operacional de marca que impõe estratégia antes de qualquer geração cara, fidelidade rígida aos produtos físicos reais (*Product Fidelity Check*), limites editoriais de governança por pilar para combater repetições superficiais, e layout gráfico determinístico com editor semântico.

## Operating Context

Aplicação web local em Python rodando em `http://127.0.0.1:8765`, utilizando SQLite local e armazenamento de arquivos em disco, sem dependências externas pesadas ou serviços em nuvem desnecessários na V1.
O estúdio é organizado em 8 rotas operacionais integradas:
- `/inicio`: Dashboard Contextual com métricas do estúdio e controle da fila.
- `/criar`: Creative Director, Briefing Híbrido, Radar Sazonal e Banco de Ideias.
- `/calendario`: Planejamento e calendário editorial com slots de postagem.
- `/conteudo`: Criação de campanhas, storyboards e geração de imagens.
- `/biblioteca`: Acervo de produtos, referências visuais, prompts e versões.
- `/insights`: Monitoramento operacional, latência de provedores e métricas de conteúdo.
- `/marca`: Brand Bible, Product Bible e diretrizes visuais.
- `/configuracoes`: Governança de custos, tetos de orçamento e chaves de provedores.

## Capabilities and Constraints

- **Briefing Híbrido**: Entrada livre em linguagem natural com estruturação progressiva em objetivos canônicos, tom visual e checagem de conflitos com a marca oficial.
- **Governança Editorial**: Banco de ideias com teto estrito de no máximo 5 ideias ativas por pilar, retenção de motivos de rejeição e fixação no topo.
- **Pipelines Multimodelo**: Geração visual multimodelo com controle de fidelidade ao produto e simulação de custos em tempo real.
- **Command Bar**: Barra de comandos com suporte a linguagem natural para navegação rápida e ações no estúdio.
- **Restrição Firme**: Dados comerciais (faturamento, inventário real) nunca podem ser inventados; publicação em redes e consumo de provedores pagos exigem aprovação explícita.

## Brand Commitments

- **Nome da Marca**: KIROS Aromas (Sorocaba · SP).
- **Assinatura & Voz**: "Aromas para casa. Presença com intenção." Tom acolhedor, sofisticado, sensorial, calmo e descomplicado.
- **Identidade Visual**: Estética editorial contemporânea e minimalista inspirada no Copy.ai (fontes Geist para títulos e Inter para textos, paleta de grafites `#171717`/`#566b76`, acento em roxo elétrico `#693edf`, gradiente arquitetural de 3 paradas `#29007a` → `#4514a6` → `#693edf`, bordas finas `#e0e0e0` e raio de 4px).

## Evidence on Hand

- Especificação mestre completa da V1 em `docs/kiros-studio-v1-spec.md`.
- Tokens e sistema de design documentados em `docs/copy-ai.design.md`.
- Arquitetura hexagonal/modular implementada em `kiros/`.
- Suíte de testes automatizados com testes HTTP e smoke tests aprovados (`scripts/smoke.py`, `tests/`).
- Aplicação ativa e testada servindo em `http://127.0.0.1:8765`.

## Product Principles

1. **Estratégia antes da geração**: A intenção e o briefing estruturado precedem qualquer solicitação aos modelos de IA.
2. **Aprovação antes de ações caras**: Nenhuma ação de custo financeiro, consumo de API paga ou publicação externa ocorre sem aprovação humana.
3. **Fidelidade máxima aos produtos reais**: Proibição estrita de criar rótulos, frascos ou características que não correspondam aos produtos físicos da KIROS.
4. **Determinismo e eficiência**: Regras de negócio, cálculos, filtros, orçamentos e layouts são determinísticos no código backend; LLMs atuam como ferramentas especializadas, não como decisores de infraestrutura.
5. **Memória e aprendizado contínuo**: Correções e sugestões manuais do operador enriquecem a biblioteca de prompts e a memória contextual da marca.

## Accessibility & Inclusion

Interface web com conformidade de contraste, suporte integral à navegação por teclado (`.skip` para pular para o conteúdo principal), foco visível em todos os formulários e botões, e estruturação semântica com tags `aria-current` e labels explícitos.
