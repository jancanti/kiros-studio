"""Biblioteca de Templates e Governança de Layout (Seção 30).

Gerencia:
- Templates aprovados nas famílias: editorial_minimalist, lifestyle_natural, split_balanced, bold_modern.
- Estados: active, archived, experimental.
- Regras de composição e adaptação.
- Salvamento de composições aprovadas como novos templates.
- Autorização estrita para templates experimentais.
- Detecção de sobreuso de templates para manter a diversidade visual da marca (Seções 30 e 32).
"""
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
import uuid

from kiros.infrastructure.local import SQLiteDatabase
from kiros.layout.models import (
    FORMAT_4_5,
    FORMAT_9_16,
    TEMPLATE_ACTIVE,
    TEMPLATE_ARCHIVED,
    TEMPLATE_EXPERIMENTAL,
    VALID_TEMPLATE_STATUSES,
    FAMILY_EDITORIAL_MINIMALIST,
    FAMILY_LIFESTYLE_NATURAL,
    FAMILY_SPLIT_BALANCED,
    FAMILY_BOLD_MODERN,
    VALID_LAYOUT_FAMILIES,
    HeadlineElement,
    ImageElement,
    LogoElement,
    CTAElement,
    DecorativeElement,
    SlideLayout,
    LayoutTemplate,
    ExperimentalTemplateUnauthorizedError,
    LayoutValidationError,
)


class TemplateLibrary:
    """Biblioteca de templates de layout com governança de estados, autorização de experimentais e detecção de sobreuso."""

    def __init__(self, db: SQLiteDatabase):
        self.db = db
        self.ensure_default_templates()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def ensure_default_templates(self):
        """Garante a existência dos templates padrão aprovados e experimentais da KIROS."""
        templates_to_seed = [
            {
                'id': 'tpl-editorial-minimalist',
                'name': 'Editorial Minimalista',
                'family': FAMILY_EDITORIAL_MINIMALIST,
                'status': TEMPLATE_ACTIVE,
                'supported_formats': [FORMAT_4_5, FORMAT_9_16],
                'composition_rules': {
                    'hierarchy': 'Generoso respiro visual, headline suave no topo e produto no centro.',
                    'spacing': 'ample',
                    'text_contrast': 'high',
                },
                'default_elements': {
                    'headline': {'font_family': 'Rubik', 'font_size': 52, 'color': '#1f2421', 'font_weight': 600},
                    'image': {'framing': 'medium', 'lighting': 'natural_lateral', 'scale': 1.0},
                    'logo': {'brand_name': 'KIROS', 'color': '#273b32'},
                    'cta': {'style': 'pill', 'bg_color': '#273b32', 'text_color': '#ffffff'},
                    'decorative': {'kind': 'badge', 'label': 'LINHA ESSENCIAL'},
                },
            },
            {
                'id': 'tpl-lifestyle-natural',
                'name': 'Lifestyle Luz Natural',
                'family': FAMILY_LIFESTYLE_NATURAL,
                'status': TEMPLATE_ACTIVE,
                'supported_formats': [FORMAT_4_5, FORMAT_9_16],
                'composition_rules': {
                    'hierarchy': 'Ambiente acolhedor com luz lateral do fim de tarde, foco na atmosfera botânica.',
                    'spacing': 'balanced',
                    'text_contrast': 'medium',
                },
                'default_elements': {
                    'headline': {'font_family': 'Rubik', 'font_size': 50, 'color': '#2c221b', 'font_weight': 500},
                    'image': {'framing': 'wide', 'lighting': 'golden_hour', 'scale': 1.05},
                    'logo': {'brand_name': 'KIROS', 'color': '#422510'},
                    'cta': {'style': 'pill', 'bg_color': '#422510', 'text_color': '#ffeed6'},
                    'decorative': {'kind': 'badge', 'label': 'EDIÇÃO LIMITADA'},
                },
            },
            {
                'id': 'tpl-split-balanced',
                'name': 'Divisão Equilibrada',
                'family': FAMILY_SPLIT_BALANCED,
                'status': TEMPLATE_ACTIVE,
                'supported_formats': [FORMAT_4_5, FORMAT_9_16],
                'composition_rules': {
                    'hierarchy': 'Equilíbrio simétrico entre bloco editorial de texto e detalhe macro do produto.',
                    'spacing': 'structured',
                    'text_contrast': 'high',
                },
                'default_elements': {
                    'headline': {'font_family': 'Rubik', 'font_size': 54, 'color': '#1a221e', 'font_weight': 700},
                    'image': {'framing': 'detail', 'lighting': 'soft_studio', 'scale': 1.15},
                    'logo': {'brand_name': 'KIROS', 'color': '#1a221e'},
                    'cta': {'style': 'pill', 'bg_color': '#1a221e', 'text_color': '#ffffff'},
                    'decorative': {'kind': 'divider', 'stroke_color': '#1a221e'},
                },
            },
            {
                'id': 'tpl-bold-modern',
                'name': 'Moderno Tipográfico',
                'family': FAMILY_BOLD_MODERN,
                'status': TEMPLATE_ACTIVE,
                'supported_formats': [FORMAT_4_5, FORMAT_9_16],
                'composition_rules': {
                    'hierarchy': 'Tipografia impactante com alta densidade de informação e corte preciso.',
                    'spacing': 'compact',
                    'text_contrast': 'maximum',
                },
                'default_elements': {
                    'headline': {'font_family': 'Rubik', 'font_size': 58, 'color': '#111412', 'font_weight': 700},
                    'image': {'framing': 'close-up', 'lighting': 'dramatic', 'scale': 1.1},
                    'logo': {'brand_name': 'KIROS', 'color': '#111412'},
                    'cta': {'style': 'pill', 'bg_color': '#111412', 'text_color': '#ffffff'},
                    'decorative': {'kind': 'badge', 'label': 'DESIGN CONTEMPORÂNEO'},
                },
            },
            {
                'id': 'tpl-experimental-botanical',
                'name': 'Experimental Botânico & Brutalista',
                'family': FAMILY_BOLD_MODERN,
                'status': TEMPLATE_EXPERIMENTAL,
                'supported_formats': [FORMAT_4_5, FORMAT_9_16],
                'composition_rules': {
                    'hierarchy': 'Composição avant-garde com grid assimétrico e linhas estruturais de concreto/madeira.',
                    'spacing': 'asymmetric',
                    'text_contrast': 'experimental',
                },
                'default_elements': {
                    'headline': {'font_family': 'Rubik', 'font_size': 60, 'color': '#1f2d24', 'font_weight': 700},
                    'image': {'framing': 'overhead', 'lighting': 'diffused', 'scale': 1.2},
                    'logo': {'brand_name': 'KIROS', 'color': '#1f2d24'},
                    'cta': {'style': 'pill', 'bg_color': '#1f2d24', 'text_color': '#eef5f0'},
                    'decorative': {'kind': 'frame', 'stroke_color': '#1f2d24'},
                },
            },
        ]

        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            for tpl in templates_to_seed:
                exists = conn.execute('SELECT 1 FROM layout_templates WHERE id=?', (tpl['id'],)).fetchone()
                if not exists:
                    conn.execute(
                        '''INSERT INTO layout_templates (id, name, family, status, supported_formats_json, composition_rules_json, default_elements_json, usage_count, created_at, updated_at, provenance)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 'system.seed')''',
                        (
                            tpl['id'],
                            tpl['name'],
                            tpl['family'],
                            tpl['status'],
                            json.dumps(tpl['supported_formats']),
                            json.dumps(tpl['composition_rules'], ensure_ascii=False),
                            json.dumps(tpl['default_elements'], ensure_ascii=False),
                            now,
                            now,
                        ),
                    )

    def list_templates(self, status: Optional[str] = None, family: Optional[str] = None) -> List[LayoutTemplate]:
        """Retorna lista de templates filtrados por estado ou família."""
        query = 'SELECT * FROM layout_templates'
        params = []
        conds = []
        if status:
            conds.append('status=?')
            params.append(status)
        if family:
            conds.append('family=?')
            params.append(family)
        if conds:
            query += ' WHERE ' + ' AND '.join(conds)
        query += ' ORDER BY usage_count DESC, created_at ASC'

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [
                LayoutTemplate(
                    id=r['id'],
                    name=r['name'],
                    family=r['family'],
                    status=r['status'],
                    supported_formats=json.loads(r['supported_formats_json']),
                    composition_rules=json.loads(r['composition_rules_json']),
                    default_elements=json.loads(r['default_elements_json']),
                    usage_count=int(r['usage_count']),
                    last_used_at=r['last_used_at'],
                    created_at=r['created_at'],
                    updated_at=r['updated_at'],
                    provenance=r['provenance'],
                )
                for r in rows
            ]

    def get_template(self, template_id: str) -> Optional[LayoutTemplate]:
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            r = conn.execute('SELECT * FROM layout_templates WHERE id=?', (template_id,)).fetchone()
            if not r:
                return None
            return LayoutTemplate(
                id=r['id'],
                name=r['name'],
                family=r['family'],
                status=r['status'],
                supported_formats=json.loads(r['supported_formats_json']),
                composition_rules=json.loads(r['composition_rules_json']),
                default_elements=json.loads(r['default_elements_json']),
                usage_count=int(r['usage_count']),
                last_used_at=r['last_used_at'],
                created_at=r['created_at'],
                updated_at=r['updated_at'],
                provenance=r['provenance'],
            )

    def apply_template(
        self,
        template_id: str,
        layout: SlideLayout,
        experimental_authorized: bool = False,
    ) -> SlideLayout:
        """Aplica as regras e elementos de um template a um layout de slide.

        REQUISITO: Templates experimentais exigem autorização (Seção 30 / M07-A04).
        """
        tpl = self.get_template(template_id)
        if not tpl:
            raise LayoutValidationError(f"Template '{template_id}' não encontrado.")

        # Governança de templates experimentais
        if tpl.status == TEMPLATE_EXPERIMENTAL and not experimental_authorized:
            raise ExperimentalTemplateUnauthorizedError(
                f"O template '{tpl.name}' é experimental e exige autorização explícita para uso em produção (Seção 30)."
            )

        if tpl.status == TEMPLATE_ARCHIVED:
            raise LayoutValidationError(f"O template '{tpl.name}' está arquivado e não pode ser aplicado.")

        defaults = tpl.default_elements

        # Atualiza elementos do layout respeitando o template
        if 'headline' in defaults:
            h_def = defaults['headline']
            if 'font_family' in h_def:
                layout.headline.font_family = h_def['font_family']
            if 'font_size' in h_def:
                layout.headline.font_size = h_def['font_size']
            if 'color' in h_def:
                layout.headline.color = h_def['color']
            if 'font_weight' in h_def:
                layout.headline.font_weight = h_def['font_weight']

        if 'image' in defaults:
            i_def = defaults['image']
            if 'framing' in i_def:
                layout.image.framing = i_def['framing']
            if 'lighting' in i_def:
                layout.image.lighting = i_def['lighting']
            if 'scale' in i_def:
                layout.image.scale = i_def['scale']

        if 'logo' in defaults:
            l_def = defaults['logo']
            if 'color' in l_def:
                layout.logo.color = l_def['color']

        if 'cta' in defaults:
            c_def = defaults['cta']
            if 'bg_color' in c_def:
                layout.cta.bg_color = c_def['bg_color']
            if 'text_color' in c_def:
                layout.cta.text_color = c_def['text_color']
            if 'style' in c_def:
                layout.cta.style = c_def['style']

        if 'decorative' in defaults:
            d_def = defaults['decorative']
            if 'kind' in d_def:
                layout.decorative.kind = d_def['kind']
            if 'label' in d_def:
                layout.decorative.label = d_def['label']
            if 'stroke_color' in d_def:
                layout.decorative.stroke_color = d_def['stroke_color']

        layout.template_id = tpl.id
        now = self._now()
        layout.updated_at = now

        # Incrementa contador de uso e atualiza timestamp no banco
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                'UPDATE layout_templates SET usage_count=usage_count+1, last_used_at=?, updated_at=? WHERE id=?',
                (now, now, tpl.id),
            )
            conn.execute(
                '''UPDATE slide_layouts
                   SET template_id=?, elements_json=?, updated_at=?
                   WHERE id=?''',
                (
                    tpl.id,
                    json.dumps(layout.to_dict()['elements'], ensure_ascii=False),
                    now,
                    layout.id,
                ),
            )

        return layout

    def detect_overuse(self, template_id: str, threshold_ratio: float = 0.35) -> Dict[str, Any]:
        """Detecta sobreuso do template em relação ao total de layouts/campanhas para evitar repetição (Seções 30 e 32)."""
        tpl = self.get_template(template_id)
        if not tpl:
            raise LayoutValidationError(f"Template '{template_id}' não encontrado.")

        with sqlite3.connect(self.db.path) as conn:
            total_layouts = conn.execute('SELECT COUNT(*) FROM slide_layouts').fetchone()[0]
            template_layouts = conn.execute('SELECT COUNT(*) FROM slide_layouts WHERE template_id=?', (template_id,)).fetchone()[0]

        # Considera sobreuso se usado pelo menos 3 vezes E representar mais que threshold_ratio (35%) dos layouts totais
        ratio = (template_layouts / total_layouts) if total_layouts > 0 else 0.0
        is_overused = (template_layouts >= 3 and ratio >= threshold_ratio)

        recommended_alternatives = [
            f for f in VALID_LAYOUT_FAMILIES if f != tpl.family
        ]

        return {
            'template_id': tpl.id,
            'template_name': tpl.name,
            'family': tpl.family,
            'template_usage_count': template_layouts,
            'total_layouts_count': total_layouts,
            'usage_ratio': round(ratio, 3),
            'is_overused': is_overused,
            'warning': (
                f"Alerta de sobreuso: o template '{tpl.name}' está em {int(ratio * 100)}% dos layouts recentes ({template_layouts}/{total_layouts}). "
                f"Recomenda-se variar para as famílias: {', '.join(recommended_alternatives)} (Seção 32)."
            ) if is_overused else None,
            'recommended_families': recommended_alternatives if is_overused else [],
        }

    def save_composition_as_template(
        self,
        layout: SlideLayout,
        name: str,
        family: str,
        status: str = TEMPLATE_ACTIVE,
        provenance_source: str = 'user',
    ) -> LayoutTemplate:
        """Salva uma composição aprovada como novo template na biblioteca (Seção 30)."""
        clean_name = (name or '').strip()
        if not clean_name:
            raise LayoutValidationError("Nome do template é obrigatório.")
        if family not in VALID_LAYOUT_FAMILIES:
            raise LayoutValidationError(f"Família de layout inválida: '{family}'. Válidas: {', '.join(VALID_LAYOUT_FAMILIES)}")
        if status not in VALID_TEMPLATE_STATUSES:
            raise LayoutValidationError(f"Estado de template inválido: '{status}'.")

        tpl_id = f"tpl-custom-{uuid.uuid4().hex[:10]}"
        now = self._now()

        default_elements = {
            'headline': {
                'font_family': layout.headline.font_family,
                'font_size': layout.headline.font_size,
                'font_weight': layout.headline.font_weight,
                'color': layout.headline.color,
            },
            'image': {
                'framing': layout.image.framing,
                'lighting': layout.image.lighting,
                'scale': layout.image.scale,
            },
            'logo': {
                'brand_name': layout.logo.brand_name,
                'color': layout.logo.color,
            },
            'cta': {
                'style': layout.cta.style,
                'bg_color': layout.cta.bg_color,
                'text_color': layout.cta.text_color,
            },
            'decorative': {
                'kind': layout.decorative.kind,
                'label': layout.decorative.label,
                'stroke_color': layout.decorative.stroke_color,
            },
        }

        composition_rules = {
            'origin_slide_id': layout.slide_id,
            'origin_campaign_id': layout.campaign_id,
            'format_saved': layout.format,
            'was_approved': layout.is_approved,
        }

        template = LayoutTemplate(
            id=tpl_id,
            name=clean_name,
            family=family,
            status=status,
            supported_formats=[FORMAT_4_5, FORMAT_9_16],
            composition_rules=composition_rules,
            default_elements=default_elements,
            usage_count=1,
            last_used_at=now,
            created_at=now,
            updated_at=now,
            provenance=f"{provenance_source}:save_composition",
        )

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO layout_templates (id, name, family, status, supported_formats_json, composition_rules_json, default_elements_json, usage_count, last_used_at, created_at, updated_at, provenance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)''',
                (
                    template.id,
                    template.name,
                    template.family,
                    template.status,
                    json.dumps(template.supported_formats),
                    json.dumps(template.composition_rules, ensure_ascii=False),
                    json.dumps(template.default_elements, ensure_ascii=False),
                    now,
                    now,
                    now,
                    template.provenance,
                ),
            )

        return template

    def archive_template(self, template_id: str) -> LayoutTemplate:
        """Arquiva um template, impedindo nova seleção para campanhas."""
        tpl = self.get_template(template_id)
        if not tpl:
            raise LayoutValidationError(f"Template '{template_id}' não encontrado.")

        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute('UPDATE layout_templates SET status=?, updated_at=? WHERE id=?', (TEMPLATE_ARCHIVED, now, template_id))
        tpl.status = TEMPLATE_ARCHIVED
        tpl.updated_at = now
        return tpl

