"""Creative Director: serviço estratégico central da V1 (Seção 9).

O Creative Director é o cérebro estratégico; modelos de IA são ferramentas.
Interpreta briefings livres, recomenda objetivos, consulta marca/produtos/memória por interfaces,
seleciona produtos sem dados comerciais e registra proveniência em decisões estratégicas.
"""
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence

from kiros.context import ContextOptimizer
from kiros.core.contracts import LLMProvider, Provenance
from kiros.director.ideas import IdeaBank
from kiros.director.memory import MemoryStore, ConflictReport
from kiros.library import Library


SUPPORTED_OBJECTIVES = (
    'vendas',
    'lançamento',
    'awareness',
    'engajamento',
    'relacionamento',
    'educação',
    'tráfego',
    'sazonal',
    'personalizado',
)


class CreativeDirector:
    """Diretor Criativo: orquestração de estratégia, contexto, briefing híbrido e banco de ideias."""

    def __init__(
        self,
        llm: LLMProvider,
        library: Optional[Library] = None,
        memory: Optional[MemoryStore] = None,
        idea_bank: Optional[IdeaBank] = None,
    ):
        self.llm = llm
        self.library = library
        self.memory = memory
        self.idea_bank = idea_bank

    def connection_preview(self) -> str:
        """Diagnóstico local da porta; não é planejamento de campanha."""
        return self.llm.complete('connection_preview')

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def recommend_objective(self, briefing_text: str) -> Dict[str, Any]:
        """Recomenda objetivo principal, secundário, justificativa e nível de confiança (Seção 12)."""
        text = (briefing_text or '').lower()

        if re.search(r'\b(lançar|lançamento|novidade|chegou|novo produto|nova linha|novo aroma)\b', text):
            primary = 'lançamento'
            secondary = 'awareness'
            justification = 'O briefing foca na apresentação de uma novidade ao público da marca.'
            confidence = 0.94
        elif re.search(r'\b(vender|venda|vendas|conversão|comprar|promoção|faturamento)\b', text):
            primary = 'vendas'
            secondary = 'tráfego'
            justification = 'Foco em geração de receita direta e tração comercial imediata.'
            confidence = 0.92
        elif re.search(r'\b(natal|mães|namorados|páscoa|sazonal|fim de ano)\b', text):
            primary = 'sazonal'
            secondary = 'vendas'
            justification = 'Campanha orientada a momento do calendário de presentes e rituais.'
            confidence = 0.95
        elif re.search(r'\b(aprender|educar|educativo|como usar|dicas|pirâmide|notas|guia)\b', text):
            primary = 'educação'
            secondary = 'relacionamento'
            justification = 'Conteúdo informativo sobre uso, aromacologia e cuidado com o produto.'
            confidence = 0.90
        elif re.search(r'\b(conectar|comunidade|conversa|história|bastidores|afeto|agradecer)\b', text):
            primary = 'relacionamento'
            secondary = 'engajamento'
            justification = 'Fortalecimento de vínculo afetivo e proximidade com clientes fieis.'
            confidence = 0.88
        elif re.search(r'\b(mostrar|conhecer|alcance|descobrir|sofisticado|visibilidade|apresentar|novos seguidores)\b', text):
            primary = 'awareness'
            secondary = 'engajamento'
            justification = 'Expansão de reconhecimento e apresentação estética da marca a novos públicos.'
            confidence = 0.89
        else:
            primary = 'awareness'
            secondary = 'relacionamento'
            justification = 'Objetivo inicial equilibrado para construção de presença visual e estética.'
            confidence = 0.75

        return {
            'primary_objective': primary,
            'secondary_objective': secondary,
            'justification': justification,
            'confidence': confidence,
        }

    def interpret_briefing(
        self,
        freeform_text: str,
        custom_objective: Optional[str] = None,
        provenance: Optional[Provenance] = None,
    ) -> Dict[str, Any]:
        """Converte linguagem livre progressivamente em dados estruturados com perguntas agrupadas mínimas (Seção 11)."""
        raw = (freeform_text or '').strip()
        if not raw:
            raise ValueError('Texto do briefing não pode ser vazio.')

        obj_rec = self.recommend_objective(raw)
        final_objective = custom_objective if custom_objective in SUPPORTED_OBJECTIVES else obj_rec['primary_objective']

        # Extração heurística de atributos estruturados
        inferred_tone = 'Sofisticado, acolhedor e contemplativo'
        if 'minimalista' in raw.lower() or 'moderno' in raw.lower():
            inferred_tone = 'Minimalista, moderno e contemporâneo'
        elif 'afetuoso' in raw.lower() or 'aconchego' in raw.lower():
            inferred_tone = 'Afetuoso, intimista e caloroso'

        # Perguntas mínimas agrupadas se informações críticas não forem deduzíveis
        questions = []
        has_product_mention = any(w in raw.lower() for w in ('vela', 'difusor', 'aroma', 'home spray', 'produto'))
        if not has_product_mention:
            questions.append({
                'group': 'Produtos e Foco',
                'question': 'Qual produto ou linha será o ponto focal desta campanha (velas, difusores ou linha completa)?',
                'required': True,
            })

        has_audience_mention = any(w in raw.lower() for w in ('público', 'clientes', 'para quem', 'presente', 'casa'))
        if not has_audience_mention:
            questions.append({
                'group': 'Público e Ocasião',
                'question': 'A campanha é voltada para autocuidado pessoal ou compra de presentes?',
                'required': False,
            })

        prov_source = provenance.source if provenance else 'user'
        structured = {
            'raw_briefing': raw,
            'summary': f"Conceito estruturado: {raw[:120]}..." if len(raw) > 120 else f"Conceito estruturado: {raw}",
            'primary_objective': final_objective,
            'secondary_objective': obj_rec['secondary_objective'],
            'objective_justification': obj_rec['justification'],
            'confidence': obj_rec['confidence'],
            'visual_tone': inferred_tone,
            'funnel_stage': 'Descoberta' if final_objective in ('awareness', 'educação') else 'Conversão',
            'suggested_pillar': 'produtos' if has_product_mention else 'lifestyle',
            'grouped_questions': questions,
            'status': 'structured_draft',
            'recorded_at': self._now(),
            'provenance': prov_source,
        }

        # Registra decisão estratégica se o memory store estiver disponível
        if self.memory and provenance:
            self.memory.record_decision(
                decision_type='briefing_interpretation',
                summary=f"Briefing estruturado com objetivo '{final_objective}'",
                details=structured,
                provenance=provenance,
            )

        return structured

    def select_products_for_concept(
        self,
        theme: str,
        attributes_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Seleciona produtos para a ideia criativa SEM depender de dados comerciais (M03-A06)."""
        if not self.library:
            return []

        products = self.library.list_products()
        if not products:
            return []

        theme_clean = (theme or '').lower()
        keywords = [w for w in re.findall(r'\b[a-z0-9]{3,}\b', theme_clean) if w not in {'com', 'para', 'uma', 'seu', 'sua'}]
        scored = []

        for p in products:
            p_detail = self.library.product(p['id'])
            # Coleta atributos de produto cadastrados na biblioteca
            attrs = p_detail.get('attributes', {})
            # Não inventa nem exige dados de vendas ou estoque comercial
            p_name = p['name'].lower()

            if not keywords:
                score = 1
            else:
                score = sum(2 for w in keywords if w in p_name) + sum(1 for w in keywords if any(w in str(v).lower() for v in attrs.values()))

            if score > 0:
                scored.append((score, {
                    'product_id': p['id'],
                    'name': p['name'],
                    'attributes': attrs,
                    'selection_reason': f"Compatibilidade visual e conceitual com o tema '{theme}'",
                }))

        scored.sort(key=lambda x: -x[0])
        selected = [item for _, item in scored]

        # Se nenhum produto deu match específico no tema, retorna os produtos disponíveis como base de criação
        if not selected and products:
            selected = [{
                'product_id': p['id'],
                'name': p['name'],
                'attributes': self.library.product(p['id']).get('attributes', {}),
                'selection_reason': 'Produto do catálogo selecionado como base criativa geral',
            } for p in products[:3]]

        return selected

    def check_conflicts(
        self,
        candidate_data: Dict[str, Any],
        product_id: Optional[str] = None,
        candidate_source: str = 'user_briefing',
    ) -> List[ConflictReport]:
        """Consulta marca e produto oficiais e verifica se há divergências (Seção 49 e M03-A05)."""
        if not self.memory or not self.library:
            return []

        official_brand = self.library.brand_for()
        official_product = self.library.product(product_id) if product_id else None

        return self.memory.detect_conflicts(
            candidate_data=candidate_data,
            official_brand=official_brand,
            official_product=official_product,
            candidate_source=candidate_source,
        )

    def consult_relevant_context(
        self,
        brand_keys: Optional[Sequence[str]] = None,
        product_id: Optional[str] = None,
        product_fields: Optional[Sequence[str]] = None,
        memory_types: Optional[Sequence[str]] = None,
        memory_keys: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Consulta marca, produto e memória relevante por interfaces e compacta contexto (M03-A02, M03-A05)."""
        context: Dict[str, Any] = {}
        if self.library:
            if brand_keys:
                official_brand = self.library.brand_for()
                context['brand'] = ContextOptimizer.select_brand_context(official_brand, brand_keys)
            if product_id and product_fields:
                prod = self.library.product(product_id)
                attrs = prod.get('attributes', {})
                context['product'] = ContextOptimizer.select_product_context(attrs, product_fields)
        if self.memory and (memory_types or memory_keys):
            mems = self.memory.query_memories(memory_types=memory_types, keys=memory_keys, limit=10)
            context['memories'] = self.memory.compact_memories(mems)
        return context

    def create_storyboard_concept(
        self,
        briefing_text: str,
        visual_tone: str = 'Minimalista, acolhedor e contemporâneo',
        num_slides: int = 3,
    ) -> List[Dict[str, Any]]:
        """Gera conceitos de storyboard estruturados a partir do briefing (Seções 9 e 10)."""
        raw = (briefing_text or 'Velas aromáticas em ambiente acolhedor').strip()
        slides = []

        slides.append({
            'title': 'Atmosfera e Cenário',
            'visual_prompt': f"Cena editorial em plano aberto: {raw}. Luz natural difusa, composição acolhedora em tons terrosos e madeira clara. Tom: {visual_tone}.",
            'framing': 'wide',
            'caption_draft': 'Onde o silêncio encontra o aconchego olfativo.',
            'engine_override': 'gemini:imagen-3.0-generate-002',
        })

        if num_slides >= 2:
            slides.append({
                'title': 'Presença e Detalhes Sensoriais',
                'visual_prompt': f"Plano médio focado: vela aromática ou difusor sobre mesa de apoio nobre com reflexos sutis. {raw}. Estilo editorial minimalista KIROS.",
                'framing': 'medium',
                'caption_draft': 'Criado para ancorar momentos de presença e desaceleração.',
                'engine_override': 'gemini:imagen-3.0-generate-002',
            })

        if num_slides >= 3:
            slides.append({
                'title': 'Texturas e Acabamento de Objeto',
                'visual_prompt': f"Plano detalhe macro: textura do vidro âmbar fosco, cera vegetal e pavio trançado. {raw}.",
                'framing': 'detail',
                'caption_draft': 'Cada camada olfativa pensada para transformar o seu espaço.',
                'engine_override': 'openai:dall-e-3',
            })

        return slides[:num_slides]
