"""Modelos e contratos de dados para Layout, Editor Semântico e Templates (Seções 28, 29, 30)."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Tuple

FORMAT_4_5 = '4:5'
FORMAT_9_16 = '9:16'
VALID_FORMATS = (FORMAT_4_5, FORMAT_9_16)

FORMAT_DIMENSIONS: Dict[str, Tuple[int, int]] = {
    FORMAT_4_5: (1080, 1350),   # Proporção 0.8 (Feed Portrait Instagram)
    FORMAT_9_16: (1080, 1920),  # Proporção 0.5625 (Stories/Reels Instagram)
}

# Safe areas para evitar cortes de interface do Instagram
SAFE_AREAS: Dict[str, Dict[str, int]] = {
    FORMAT_4_5: {
        'top': 60,
        'bottom': 60,
        'left': 60,
        'right': 60,
    },
    FORMAT_9_16: {
        'top': 250,     # Cabeçalho do Stories (foto de perfil, nome, barras de status)
        'bottom': 350,  # Rodapé do Stories (caixa de resposta, botões de ação e direct)
        'left': 60,
        'right': 60,
    },
}

ELEMENT_TYPES = ('headline', 'image', 'logo', 'cta', 'decorative')

PROTECTION_FREE = 'free'            # Verde: livre (posição, escala, enquadramento, iluminação)
PROTECTION_PROTECTED = 'protected'  # Amarelo: protected (alerta e confirmação explícita)
PROTECTION_CRITICAL = 'critical'    # Vermelho: critical (bloquear, unlock explícito auditado)
VALID_PROTECTION_LEVELS = (PROTECTION_FREE, PROTECTION_PROTECTED, PROTECTION_CRITICAL)

TEMPLATE_ACTIVE = 'active'
TEMPLATE_ARCHIVED = 'archived'
TEMPLATE_EXPERIMENTAL = 'experimental'
VALID_TEMPLATE_STATUSES = (TEMPLATE_ACTIVE, TEMPLATE_ARCHIVED, TEMPLATE_EXPERIMENTAL)

FAMILY_EDITORIAL_MINIMALIST = 'editorial_minimalist'
FAMILY_LIFESTYLE_NATURAL = 'lifestyle_natural'
FAMILY_SPLIT_BALANCED = 'split_balanced'
FAMILY_BOLD_MODERN = 'bold_modern'
VALID_LAYOUT_FAMILIES = (
    FAMILY_EDITORIAL_MINIMALIST,
    FAMILY_LIFESTYLE_NATURAL,
    FAMILY_SPLIT_BALANCED,
    FAMILY_BOLD_MODERN,
)

VALID_FRAMINGS = ('wide', 'medium', 'close-up', 'detail', 'overhead')
VALID_LIGHTINGS = ('natural_lateral', 'golden_hour', 'soft_studio', 'dramatic', 'diffused')


class LayoutValidationError(ValueError):
    """Lançado quando os parâmetros de layout são inválidos ou violam restrições do motor."""
    pass


class ProtectedAttributeError(ValueError):
    """Lançado quando um atributo amarelo/protected é modificado sem confirmação explícita."""
    pass


class CriticalAttributeLockedError(PermissionError):
    """Lançado quando um atributo vermelho/critical tenta ser alterado sem unlock auditado."""
    pass


class ExperimentalTemplateUnauthorizedError(PermissionError):
    """Lançado quando um template experimental tenta ser aplicado sem autorização explícita."""
    pass


@dataclass
class HeadlineElement:
    text: str
    font_family: str = 'Rubik'
    font_size: int = 54
    font_weight: int = 600
    line_height: float = 1.18
    letter_spacing: float = -0.5
    text_align: str = 'left'  # 'left', 'center', 'right'
    color: str = '#1f2421'
    position_x: int = 80
    position_y: int = 140
    max_width: int = 920

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HeadlineElement':
        return cls(
            text=str(data.get('text', '')),
            font_family=str(data.get('font_family', 'Rubik')),
            font_size=int(data.get('font_size', 54)),
            font_weight=int(data.get('font_weight', 600)),
            line_height=float(data.get('line_height', 1.18)),
            letter_spacing=float(data.get('letter_spacing', -0.5)),
            text_align=str(data.get('text_align', 'left')),
            color=str(data.get('color', '#1f2421')),
            position_x=int(data.get('position_x', 80)),
            position_y=int(data.get('position_y', 140)),
            max_width=int(data.get('max_width', 920)),
        )


@dataclass
class ImageElement:
    asset_id: Optional[str] = None
    framing: str = 'medium'
    scale: float = 1.0
    position_x: int = 0
    position_y: int = 0
    lighting: str = 'natural_lateral'
    opacity: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageElement':
        return cls(
            asset_id=data.get('asset_id'),
            framing=str(data.get('framing', 'medium')),
            scale=float(data.get('scale', 1.0)),
            position_x=int(data.get('position_x', 0)),
            position_y=int(data.get('position_y', 0)),
            lighting=str(data.get('lighting', 'natural_lateral')),
            opacity=float(data.get('opacity', 1.0)),
        )


@dataclass
class LogoElement:
    brand_name: str = 'KIROS'
    variant: str = 'primary'  # 'primary', 'monochrome', 'compact'
    position_x: int = 80
    position_y: int = 70
    scale: float = 1.0
    aspect_ratio_locked: bool = True
    color: str = '#273b32'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogoElement':
        return cls(
            brand_name=str(data.get('brand_name', 'KIROS')),
            variant=str(data.get('variant', 'primary')),
            position_x=int(data.get('position_x', 80)),
            position_y=int(data.get('position_y', 70)),
            scale=float(data.get('scale', 1.0)),
            aspect_ratio_locked=bool(data.get('aspect_ratio_locked', True)),
            color=str(data.get('color', '#273b32')),
        )


@dataclass
class CTAElement:
    text: str = 'Descubra a Coleção'
    style: str = 'pill'  # 'pill', 'outline', 'minimal', 'solid'
    position_x: int = 80
    position_y: int = 1220
    font_size: int = 24
    bg_color: str = '#273b32'
    text_color: str = '#ffffff'
    padding_x: int = 36
    padding_y: int = 18
    border_radius: int = 999

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CTAElement':
        return cls(
            text=str(data.get('text', 'Descubra a Coleção')),
            style=str(data.get('style', 'pill')),
            position_x=int(data.get('position_x', 80)),
            position_y=int(data.get('position_y', 1220)),
            font_size=int(data.get('font_size', 24)),
            bg_color=str(data.get('bg_color', '#273b32')),
            text_color=str(data.get('text_color', '#ffffff')),
            padding_x=int(data.get('padding_x', 36)),
            padding_y=int(data.get('padding_y', 18)),
            border_radius=int(data.get('border_radius', 999)),
        )


@dataclass
class DecorativeElement:
    kind: str = 'badge'  # 'frame', 'divider', 'badge', 'tag', 'none'
    position_x: int = 80
    position_y: int = 1140
    width: int = 180
    height: int = 32
    stroke_color: str = 'rgba(39, 59, 50, 0.25)'
    fill_color: str = 'rgba(255, 255, 255, 0.75)'
    stroke_width: int = 1
    opacity: float = 0.95
    label: str = 'AROMAS BOTÂNICOS'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DecorativeElement':
        return cls(
            kind=str(data.get('kind', 'badge')),
            position_x=int(data.get('position_x', 80)),
            position_y=int(data.get('position_y', 1140)),
            width=int(data.get('width', 180)),
            height=int(data.get('height', 32)),
            stroke_color=str(data.get('stroke_color', 'rgba(39, 59, 50, 0.25)')),
            fill_color=str(data.get('fill_color', 'rgba(255, 255, 255, 0.75)')),
            stroke_width=int(data.get('stroke_width', 1)),
            opacity=float(data.get('opacity', 0.95)),
            label=str(data.get('label', 'AROMAS BOTÂNICOS')),
        )


@dataclass
class SlideLayout:
    id: str
    campaign_id: str
    slide_id: str
    template_id: Optional[str] = None
    format: str = FORMAT_4_5
    headline: HeadlineElement = field(default_factory=lambda: HeadlineElement(text='KIROS Aromas'))
    image: ImageElement = field(default_factory=ImageElement)
    logo: LogoElement = field(default_factory=LogoElement)
    cta: CTAElement = field(default_factory=CTAElement)
    decorative: DecorativeElement = field(default_factory=DecorativeElement)
    protection_overrides: Dict[str, Any] = field(default_factory=dict)
    is_approved: bool = False
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'slide_id': self.slide_id,
            'template_id': self.template_id,
            'format': self.format,
            'elements': {
                'headline': self.headline.to_dict(),
                'image': self.image.to_dict(),
                'logo': self.logo.to_dict(),
                'cta': self.cta.to_dict(),
                'decorative': self.decorative.to_dict(),
            },
            'protection_overrides': self.protection_overrides,
            'is_approved': self.is_approved,
            'approved_at': self.approved_at,
            'approved_by': self.approved_by,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SlideLayout':
        elements = data.get('elements') or {}
        return cls(
            id=data['id'],
            campaign_id=data['campaign_id'],
            slide_id=data['slide_id'],
            template_id=data.get('template_id'),
            format=data.get('format', FORMAT_4_5),
            headline=HeadlineElement.from_dict(elements.get('headline', {})),
            image=ImageElement.from_dict(elements.get('image', {})),
            logo=LogoElement.from_dict(elements.get('logo', {})),
            cta=CTAElement.from_dict(elements.get('cta', {})),
            decorative=DecorativeElement.from_dict(elements.get('decorative', {})),
            protection_overrides=data.get('protection_overrides', {}),
            is_approved=bool(data.get('is_approved', False)),
            approved_at=data.get('approved_at'),
            approved_by=data.get('approved_by'),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
        )


@dataclass
class LayoutTemplate:
    id: str
    name: str
    family: str
    status: str = TEMPLATE_ACTIVE
    supported_formats: List[str] = field(default_factory=lambda: [FORMAT_4_5, FORMAT_9_16])
    composition_rules: Dict[str, Any] = field(default_factory=dict)
    default_elements: Dict[str, Any] = field(default_factory=dict)
    usage_count: int = 0
    last_used_at: Optional[str] = None
    created_at: str = ''
    updated_at: str = ''
    provenance: str = 'system'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'family': self.family,
            'status': self.status,
            'supported_formats': self.supported_formats,
            'composition_rules': self.composition_rules,
            'default_elements': self.default_elements,
            'usage_count': self.usage_count,
            'last_used_at': self.last_used_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'provenance': self.provenance,
        }


@dataclass
class LayoutAuditEntry:
    id: str
    layout_id: str
    slide_id: str
    attribute_name: str
    protection_level: str
    previous_value: str
    new_value: str
    reason: str
    operator: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

