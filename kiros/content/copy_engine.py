"""Motor de geração e governança de Copy, Legendas e Voz da Marca (Seções 34, 35, 36, 37)."""
import re
from typing import Any, Dict, List, Optional, Tuple

from kiros.content.models import (
    VALID_CAPTION_MODES,
    VALID_CTA_MODES,
    PROHIBITED_AI_CLICHES,
    PROHIBITED_CTA_FORMULAS,
    NATURAL_SEO_CATEGORIES,
    EMOJI_PATTERN,
    HASHTAG_PATTERN,
    CommercialDataFabricationError,
    PriceApprovalRequiredError,
    MissingProductPriceError,
    InvalidCaptionModeError,
    ProhibitedContentError,
)


class CopyEngine:
    """Motor de redação alinhado à voz da KIROS: humana, leve, relaxada, brasileira, elegante sem rigidez."""

    def __init__(self):
        pass

    def clean_emojis_and_hashtags(self, text: str) -> str:
        """Remove emojis e hashtags automáticas do texto."""
        no_emojis = EMOJI_PATTERN.sub('', text)
        no_hashtags = HASHTAG_PATTERN.sub('', no_emojis)
        # Normaliza espaços extras
        cleaned = re.sub(r' +', ' ', no_hashtags)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        return cleaned

    def check_prohibited_elements(self, text: str) -> List[str]:
        """Identifica violações de clichês de IA, emojis ou fórmulas artificiais."""
        violations = []
        lower = text.lower()

        if EMOJI_PATTERN.search(text):
            violations.append('Uso de emojis detectado. Emojis são proibidos em legendas e CTAs (Seção 34).')

        if HASHTAG_PATTERN.search(text):
            violations.append('Hashtags detectadas. Não usar hashtags automaticamente (Seção 34).')

        for cliche in PROHIBITED_AI_CLICHES:
            if cliche in lower:
                violations.append(f'Clichê de IA detectado: "{cliche}". A voz da KIROS deve ser natural e brasileira (Seção 34).')

        for formula in PROHIBITED_CTA_FORMULAS:
            if formula in lower:
                violations.append(f'Fórmula artificial de CTA detectada: "{formula}". Evitar fórmulas prontas (Seção 36).')

        return violations

    def generate_automatic_caption(self, context: Dict[str, Any]) -> str:
        """Gera legenda automática no modo 'automatic' (Seção 35).
        
        Usa voz leve, relaxada, brasileira, com SEO natural e sem emojis ou hashtags.
        """
        product_name = context.get('product_name') or context.get('product_title') or 'Vela Aromática'
        visual_tone = context.get('visual_tone') or 'luz natural e ambiente acolhedor'
        fragrance = context.get('fragrance') or 'Alecrim & Flor de Laranjeira'
        occasion = context.get('occasion') or 'começo de manhã'

        # Estruturas autênticas de voz brasileira para a KIROS
        paragraphs = [
            f"O aroma de {fragrance.lower()} preenche a casa aos poucos. É aquele tipo de detalhe que transforma o silêncio da manhã em um respiro bom.",
            f"Feita com cera vegetal e pavio de algodão para queimar devagar, sem pressa. Perfeita para deixar na mesa de cabeceira ou ao lado de um café fresco."
        ]

        caption = "\n\n".join(paragraphs)
        return self.clean_emojis_and_hashtags(caption)

    def generate_caption_suggestions(self, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Gera 3 opções distintas de legenda no modo 'suggestions' (Seção 35)."""
        product_name = context.get('product_name', 'Vela Aromática')
        fragrance = context.get('fragrance', 'Alecrim & Algodão')

        s1_text = (
            f"Notas frescas de {fragrance.lower()} que abrem espaço para um momento calmo no meio do dia. "
            "Aroma suave que acolhe a casa sem invadir o ambiente."
        )

        s2_text = (
            f"Um ritual simples para desacelerar: acender a vela de {fragrance.lower()}, "
            "abrir a janela e deixar a luz da tarde entrar na sala."
        )

        s3_text = (
            f"Cera vegetal limpa, pavio de algodão e a delicadeza do {fragrance.lower()}. "
            "Presença sutil para o seu espaço."
        )

        return [
            {
                'title': 'Sensorial & Atmosfera',
                'style': 'sensorial',
                'text': s1_text,
                'seo_terms': ['vela aromática', 'aroma suave', 'acolhe a casa'],
            },
            {
                'title': 'Rotina & Dia a Dia',
                'style': 'rotina',
                'text': s2_text,
                'seo_terms': ['ritual simples', 'desacelerar', 'luz da tarde'],
            },
            {
                'title': 'Minimalista & Direta',
                'style': 'minimalista',
                'text': s3_text,
                'seo_terms': ['cera vegetal', 'pavio de algodão', 'presença sutil'],
            },
        ]

    def refine_user_copy(self, user_draft: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Modo 'ai_plus_user': refina o rascunho fornecido pelo operador.
        
        Preserva rigorosamente a contribuição, ideias e termos originais do usuário,
        ajustando apenas fluidez para a voz brasileira e removendo emojis/hashtags acidentais.
        """
        if not user_draft or not user_draft.strip():
            return ""

        # Remove emojis e hashtags mantendo toda a essência textual
        cleaned = self.clean_emojis_and_hashtags(user_draft.strip())

        # Ajusta pontuação e espaçamento mantendo as palavras do usuário
        sentences = [s.strip() for s in cleaned.split('\n') if s.strip()]
        refined = "\n\n".join(sentences)
        return refined

    def generate_cta(self, cta_mode: str = 'none', intent: Optional[str] = None, manual_text: str = '') -> str:
        """Gera ou valida CTA contextual (Seção 36).
        
        CTA NÃO é obrigatório. Fórmulas artificiais ('comente EU QUERO') são proibidas.
        """
        if cta_mode not in VALID_CTA_MODES:
            cta_mode = 'none'

        if cta_mode == 'none':
            return ''

        if cta_mode == 'manual':
            clean_manual = self.clean_emojis_and_hashtags(manual_text)
            violations = self.check_prohibited_elements(clean_manual)
            if violations:
                raise ProhibitedContentError("; ".join(violations))
            return clean_manual

        if cta_mode in ('automatic', 'intent_based'):
            intent_key = (intent or '').lower()
            if 'descoberta' in intent_key or 'colecao' in intent_key:
                return 'Disponível no link da bio para conhecer a coleção.'
            elif 'aroma' in intent_key or 'fragrancia' in intent_key or 'escolha' in intent_key:
                return 'Para escolher o seu aroma, acesse o link da bio.'
            elif 'presente' in intent_key or 'casa' in intent_key:
                return 'Para presentear ou decorar seu espaço, o catálogo está no link da bio.'
            else:
                return 'Mais detalhes e catálogo completo no link da bio.'

        if cta_mode == 'suggestion':
            return 'Disponível no link da bio.'

        return ''

    def validate_and_format_price(
        self,
        show_price: bool,
        product_data: Optional[Dict[str, Any]] = None,
        justification: Optional[str] = None,
        approved_by: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Aplica regras de governança estrita de preço (Seção 37 e M08-A02, M08-A03).
        
        - Preço oculto por padrão (show_price=False).
        - Nunca inventar preço.
        - Se show_price=True: exige dado real da Product Bible, justificativa estratégica e aprovação explícita.
        """
        if not show_price:
            return False, None

        if not product_data:
            raise MissingProductPriceError(
                "Não é possível exibir preço: nenhum dado de produto foi fornecido da Product Bible."
            )

        # Procura preço real nos atributos do produto
        price_val = (
            product_data.get('price')
            or product_data.get('preco')
            or product_data.get('valor')
        )
        if not price_val and 'attributes' in product_data:
            attrs = product_data['attributes']
            price_val = attrs.get('price') or attrs.get('preco') or attrs.get('valor')

        if not price_val:
            raise MissingProductPriceError(
                f"Produto '{product_data.get('name', 'desconhecido')}' não possui preço real cadastrado na Product Bible. "
                "Nunca inventar preço (Seções 35 e 37)."
            )

        # Exige justificativa estratégica
        if not justification or not justification.strip():
            raise PriceApprovalRequiredError(
                "A exibição de preço exige justificativa estratégica explicando por que mostrar o preço é benéfico (Seção 37)."
            )

        # Exige aprovação explícita de operador
        if not approved_by or not approved_by.strip():
            raise PriceApprovalRequiredError(
                "A exibição de preço exige aprovação explícita de operador registrado (Seção 37)."
            )

        # Formata preço limpo (ex: "R$ 118,00" ou "R$ 118")
        clean_price = str(price_val).strip()
        if not clean_price.startswith('R$'):
            clean_price = f"R$ {clean_price}"

        return True, clean_price

    def detect_commercial_fabrication(self, text: str, allowed_price: Optional[str] = None) -> List[str]:
        """Detecta alucinação ou invenção de dados comerciais (preço, estoque, promoção, etc.)."""
        violations = []
        lower = text.lower()

        # Invenção de estoque e escassez artificial
        scarcity_triggers = [
            'últimas unidades', 'restam apenas', 'poucas peças', 'estoque acabando',
            'estoque limitado', 'quase esgotado', 'corra antes que acabe'
        ]
        for trigger in scarcity_triggers:
            if trigger in lower:
                violations.append(
                    f'Invenção de escassez comercial detectada: "{trigger}". '
                    'Nunca inventar estoque ou disponibilidade sem dado real confirmado (Seção 35).'
                )

        # Invenção de promoção ou desconto
        promo_triggers = [
            '% off', 'desconto imperdível', 'compre 1 leve 2', 'frete grátis só hoje',
            'promoção relâmpago', 'queima de estoque', 'preço especial só hoje'
        ]
        for trigger in promo_triggers:
            if trigger in lower:
                violations.append(
                    f'Invenção de promoção comercial detectada: "{trigger}". '
                    'Nunca inventar promoção ou condição comercial não oficial (Seção 35).'
                )

        # Detecção de preço inventado no texto se não for o preço oficial autorizado
        price_matches = re.findall(r'R\$\s*\d+(?:[.,]\d+)?', text)
        for pm in price_matches:
            if not allowed_price or pm.replace(' ', '') != allowed_price.replace(' ', ''):
                violations.append(
                    f'Preço não autorizado ou inventado no texto: "{pm}". '
                    'Preço só pode ser exibido se for dado real da Product Bible com justificativa e aprovação (Seção 37).'
                )

        return violations

    def build_full_caption(
        self,
        mode: str,
        text: str,
        cta_text: str = '',
        show_price: bool = False,
        price_value: Optional[str] = None,
        destination_url: str = '',
    ) -> str:
        """Monta a legenda final estruturada."""
        if mode not in VALID_CAPTION_MODES:
            raise InvalidCaptionModeError(f"Modo de legenda inválido: {mode}. Esperado: {VALID_CAPTION_MODES}")

        clean_text = self.clean_emojis_and_hashtags(text)
        parts = [clean_text]

        if show_price and price_value:
            parts.append(f"Valor: {price_value}")

        if cta_text and cta_text.strip():
            clean_cta = self.clean_emojis_and_hashtags(cta_text.strip())
            parts.append(clean_cta)
        elif destination_url and destination_url.strip():
            parts.append(f"Mais detalhes: {destination_url.strip()}")

        full = "\n\n".join(p for p in parts if p)
        return full

