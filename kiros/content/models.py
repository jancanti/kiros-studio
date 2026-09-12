"""Modelos, contratos e constantes para Copy, Legendas, Stories e Auditoria Pré-Publicação (Seções 34-38)."""
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional


VALID_CAPTION_MODES = ('automatic', 'suggestions', 'user_provided', 'ai_plus_user')
VALID_CTA_MODES = ('none', 'automatic', 'manual', 'intent_based', 'suggestion')
VALID_STORY_TYPES = ('independent', 'derived_from_campaign')
VALID_NARRATIVE_ROLES = ('hook', 'context', 'sensory_detail', 'interaction', 'closing')
VALID_INTERACTION_TYPES = ('none', 'poll', 'question_box', 'quiz', 'link_sticker')

# Clichês de IA banidos pela voz da KIROS (Seção 34)
PROHIBITED_AI_CLICHES = [
    'no mundo agitado de hoje',
    'mergulhe em uma experiência',
    'descubra a magia',
    'aconchego e sofisticação em cada detalhe',
    'não perca tempo',
    'transforme seu ambiente',
    'em um piscar de olhos',
    'cada detalhe pensado com carinho',
    'a escolha perfeita para',
    'eleve seus sentidos',
    'desperte suas sensações',
    'um toque de requinte',
    'sinônimo de elegância',
    'prepare-se para se apaixonar',
]

# Fórmulas artificiais de CTA banidas (Seções 34 e 36)
PROHIBITED_CTA_FORMULAS = [
    'comente eu quero',
    'deixe seu like',
    'salve para não esquecer',
    'marca um amigo',
    'marque alguém',
    'corre pro link da bio',
    'clique no link da bio agora mesmo',
    'arrasta pra cima',
    'digite quero nos comentários',
]

# Termos para SEO natural orgânico (Seção 35)
NATURAL_SEO_CATEGORIES = {
    'produto': ['vela aromática', 'home spray', 'difusor de varetas', 'cera vegetal de coco'],
    'fragrância': ['alecrim', 'laranja doce', 'baunilha', 'figo', 'lavanda', 'cedro'],
    'categoria': ['aromatização de ambientes', 'perfumaria botânica', 'autocuidado'],
    'ocasião': ['manhã tranquila', 'fim de tarde', 'leitura', 'banho relaxante', 'trabalho focado'],
    'casa': ['sala de estar', 'mesa de cabeceira', 'lavabo', 'cantinho do café'],
    'presentes': ['presente artesanal', 'lembrança afetiva', 'presente de casa nova'],
}

# Regex para detectar emojis em texto
# Cobre os principais blocos Unicode de emojis e pictogramas
EMOJI_PATTERN = re.compile(
    r'[\U0001F600-\U0001F64F]'  # emoticons
    r'|[\U0001F300-\U0001F5FF]'  # símbolos & pictogramas diversos
    r'|[\U0001F680-\U0001F6FF]'  # transporte & mapas
    r'|[\U0001F1E0-\U0001F1FF]'  # bandeiras
    r'|[\U0001F900-\U0001F9FF]'  # símbolos suplementares
    r'|[\U0001FA00-\U0001FA6F]'  # símbolos xadrez, etc.
    r'|[\U0001FA70-\U0001FAFF]'  # símbolos adicionais
    r'|[\U00002702-\U000027B0]'  # dingbats
    r'|[\U000024C2-\U0001F251]'  # símbolos fechados
    r'|[\U00002600-\U000026FF]'  # símbolos miscelâneos
)

# Regex para detectar hashtags
HASHTAG_PATTERN = re.compile(r'#\w+')


class ContentDomainError(Exception):
    """Erro base do domínio de Conteúdo."""
    pass


class CommercialDataFabricationError(ContentDomainError):
    """Disparado quando ocorre tentativa de inventar preço, estoque, disponibilidade ou promoção."""
    pass


class PriceApprovalRequiredError(ContentDomainError):
    """Disparado quando a exibição de preço não possui justificativa ou aprovação explícita."""
    pass


class MissingProductPriceError(ContentDomainError):
    """Disparado quando a exibição de preço é solicitada mas o produto não possui preço cadastrado na Product Bible."""
    pass


class PrePublishAuditBlockedError(ContentDomainError):
    """Disparado quando a peça de conteúdo é bloqueada na auditoria pré-publicação."""
    pass


class InvalidCaptionModeError(ContentDomainError):
    """Disparado quando o modo de legenda informado é inválido."""
    pass


class ProhibitedContentError(ContentDomainError):
    """Disparado quando conteúdo proibido (emojis, hashtags automáticas, clichês) é detectado."""
    pass


@dataclass
class CaptionContent:
    """Representa a legenda e metadados editoriais de um slide ou publicação."""
    id: str
    campaign_id: str
    slide_id: str
    mode: str = 'automatic'
    text: str = ''
    user_draft: str = ''
    suggestions: List[Dict[str, str]] = field(default_factory=list)
    tone: str = 'leve, relaxado, brasileiro'
    seo_terms: List[str] = field(default_factory=list)
    cta_mode: str = 'none'
    cta_text: str = ''
    cta_intent: Optional[str] = None
    destination_url: str = ''
    show_price: bool = False
    price_value: Optional[str] = None
    price_justification: Optional[str] = None
    price_approved_by: Optional[str] = None
    price_approved_at: Optional[str] = None
    status: str = 'draft'
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'slide_id': self.slide_id,
            'mode': self.mode,
            'text': self.text,
            'user_draft': self.user_draft,
            'suggestions': self.suggestions,
            'tone': self.tone,
            'seo_terms': self.seo_terms,
            'cta_mode': self.cta_mode,
            'cta_text': self.cta_text,
            'cta_intent': self.cta_intent,
            'destination_url': self.destination_url,
            'show_price': self.show_price,
            'price_value': self.price_value,
            'price_justification': self.price_justification,
            'price_approved_by': self.price_approved_by,
            'price_approved_at': self.price_approved_at,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


@dataclass
class StoryFrame:
    """Representa um frame individual de uma sequência de Stories (Seção 38)."""
    id: str
    sequence_id: str
    frame_order: int
    narrative_role: str
    title: str
    overlay_text: str
    visual_prompt: str
    interaction_type: str = 'none'
    interaction_data: Dict[str, Any] = field(default_factory=dict)
    interaction_justification: str = ''
    caption_draft: str = ''
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'sequence_id': self.sequence_id,
            'frame_order': self.frame_order,
            'narrative_role': self.narrative_role,
            'title': self.title,
            'overlay_text': self.overlay_text,
            'visual_prompt': self.visual_prompt,
            'interaction_type': self.interaction_type,
            'interaction_data': self.interaction_data,
            'interaction_justification': self.interaction_justification,
            'caption_draft': self.caption_draft,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


@dataclass
class StorySequence:
    """Representa o planejamento estruturado de uma sequência de Stories (Seção 38)."""
    id: str
    campaign_id: Optional[str]
    title: str
    story_type: str = 'independent'
    objective: str = ''
    frames: List[StoryFrame] = field(default_factory=list)
    status: str = 'draft'
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'title': self.title,
            'story_type': self.story_type,
            'objective': self.objective,
            'frames': [f.to_dict() for f in self.frames],
            'frames_count': len(self.frames),
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


@dataclass
class AuditCheckItem:
    """Item individual do checklist de auditoria pré-publicação."""
    check_id: str
    category: str
    title: str
    status: str  # 'passed', 'warning', 'blocked'
    message: str
    fix_suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'check_id': self.check_id,
            'category': self.category,
            'title': self.title,
            'status': self.status,
            'message': self.message,
            'fix_suggestion': self.fix_suggestion,
        }


@dataclass
class PrePublishAuditResult:
    """Resultado da auditoria pré-publicação para governança de publicação."""
    target_type: str
    target_id: str
    is_ready: bool
    checks: List[AuditCheckItem] = field(default_factory=list)
    blocked_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    operator: str = ''
    created_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'target_type': self.target_type,
            'target_id': self.target_id,
            'is_ready': self.is_ready,
            'checks': [c.to_dict() for c in self.checks],
            'blocked_reasons': self.blocked_reasons,
            'warnings': self.warnings,
            'operator': self.operator,
            'created_at': self.created_at,
        }

