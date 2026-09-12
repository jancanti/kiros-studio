"""Editor Visual Semântico com Proteção por Atributos (Seção 29).

Gerencia as alterações em layouts de slides classificadas em:
- Verde (Livre): posição, escala, enquadramento, iluminação.
- Amarelo (Protected): alerta e confirmação explícita.
- Vermelho (Critical): bloqueio por padrão, unlock explícito auditado com registro de exceção.

GARANTIA DE ISOLAMENTO:
Nunca altera a Product Bible oficial automaticamente (Seção 29 e M07-A03).
"""
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
import uuid

from kiros.infrastructure.local import SQLiteDatabase
from kiros.layout.engine import LayoutEngine
from kiros.layout.models import (
    FORMAT_4_5,
    FORMAT_9_16,
    PROTECTION_FREE,
    PROTECTION_PROTECTED,
    PROTECTION_CRITICAL,
    VALID_FRAMINGS,
    VALID_LIGHTINGS,
    HeadlineElement,
    ImageElement,
    LogoElement,
    CTAElement,
    DecorativeElement,
    SlideLayout,
    LayoutAuditEntry,
    LayoutValidationError,
    ProtectedAttributeError,
    CriticalAttributeLockedError,
)

# Classificação estrita dos atributos conforme Seção 29 da especificação
ATTRIBUTE_CLASSIFICATION: Dict[str, str] = {
    # Verde (Livre)
    'position_x': PROTECTION_FREE,
    'position_y': PROTECTION_FREE,
    'scale': PROTECTION_FREE,
    'framing': PROTECTION_FREE,
    'lighting': PROTECTION_FREE,
    'image_position_x': PROTECTION_FREE,
    'image_position_y': PROTECTION_FREE,
    'image_scale': PROTECTION_FREE,
    'image_framing': PROTECTION_FREE,
    'image_lighting': PROTECTION_FREE,

    # Amarelo (Protected - Exige alerta e confirmação)
    'headline_text': PROTECTION_PROTECTED,
    'cta_text': PROTECTION_PROTECTED,
    'font_family': PROTECTION_PROTECTED,
    'font_size': PROTECTION_PROTECTED,
    'headline_color': PROTECTION_PROTECTED,
    'cta_color': PROTECTION_PROTECTED,
    'safe_zone_override': PROTECTION_PROTECTED,
    'decorative_kind': PROTECTION_PROTECTED,
    'decorative_label': PROTECTION_PROTECTED,

    # Vermelho (Critical - Bloqueado por padrão, exige unlock explícito auditado)
    'logo_locked': PROTECTION_CRITICAL,
    'logo_aspect_ratio': PROTECTION_CRITICAL,
    'product_id': PROTECTION_CRITICAL,
    'brand_identity_lock': PROTECTION_CRITICAL,
    'product_bible_attribute': PROTECTION_CRITICAL,
}


class LayoutEditor:
    """Controlador do Editor Visual Semântico com aplicação de governança e isolamento da Product Bible."""

    def __init__(self, db: SQLiteDatabase, engine: Optional[LayoutEngine] = None, library: Optional[Any] = None):
        self.db = db
        self.engine = engine or LayoutEngine()
        self.library = library

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_layout(self, layout_id: str) -> Optional[SlideLayout]:
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM slide_layouts WHERE id=?', (layout_id,)).fetchone()
            if not row:
                return None
            return SlideLayout.from_dict({
                'id': row['id'],
                'campaign_id': row['campaign_id'],
                'slide_id': row['slide_id'],
                'template_id': row['template_id'],
                'format': row['format'],
                'elements': json.loads(row['elements_json']),
                'protection_overrides': json.loads(row['protection_overrides_json']),
                'is_approved': bool(row['is_approved']),
                'approved_at': row['approved_at'],
                'approved_by': row['approved_by'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
            })

    def get_layout_for_slide(self, slide_id: str) -> Optional[SlideLayout]:
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM slide_layouts WHERE slide_id=? ORDER BY created_at DESC LIMIT 1', (slide_id,)).fetchone()
            if not row:
                return None
            return SlideLayout.from_dict({
                'id': row['id'],
                'campaign_id': row['campaign_id'],
                'slide_id': row['slide_id'],
                'template_id': row['template_id'],
                'format': row['format'],
                'elements': json.loads(row['elements_json']),
                'protection_overrides': json.loads(row['protection_overrides_json']),
                'is_approved': bool(row['is_approved']),
                'approved_at': row['approved_at'],
                'approved_by': row['approved_by'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
            })

    def get_or_create_layout(
        self,
        campaign_id: str,
        slide_id: str,
        target_format: str = FORMAT_4_5,
        default_headline: Optional[str] = None,
        default_cta: Optional[str] = None,
    ) -> SlideLayout:
        """Recupera layout existente ou instancia um layout padrão configurado para o slide."""
        existing = self.get_layout_for_slide(slide_id)
        if existing:
            return existing

        now = self._now()
        lid = f"layout-{uuid.uuid4().hex[:12]}"
        h_text = default_headline or 'KIROS Aromas · Presença com Intenção'
        c_text = default_cta or 'Descubra a Coleção'

        layout = SlideLayout(
            id=lid,
            campaign_id=campaign_id,
            slide_id=slide_id,
            template_id=None,
            format=target_format,
            headline=HeadlineElement(text=h_text),
            image=ImageElement(framing='medium', scale=1.0, lighting='natural_lateral'),
            logo=LogoElement(brand_name='KIROS', aspect_ratio_locked=True),
            cta=CTAElement(text=c_text),
            decorative=DecorativeElement(kind='badge', label='AROMAS BOTÂNICOS'),
            created_at=now,
            updated_at=now,
        )

        # Se target_format for 9:16, adapta as posições padrão
        if target_format == FORMAT_9_16:
            layout = self.engine.adapt_format(layout, FORMAT_9_16)

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO slide_layouts (id, campaign_id, slide_id, template_id, format, elements_json, protection_overrides_json, is_approved, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)''',
                (
                    layout.id,
                    layout.campaign_id,
                    layout.slide_id,
                    layout.template_id,
                    layout.format,
                    json.dumps(layout.to_dict()['elements'], ensure_ascii=False),
                    json.dumps(layout.protection_overrides, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return layout

    def update_layout(
        self,
        layout_id: str,
        updates: Dict[str, Any],
        confirm_protected: bool = False,
        unlock_critical: bool = False,
        audit_reason: Optional[str] = None,
        unlocked_by: Optional[str] = None,
    ) -> Tuple[SlideLayout, List[str]]:
        """Aplica mutações no layout com validação rigorosa de proteção por atributo (Seção 29).

        - Verde: livre (posição, escala, enquadramento, iluminação)
        - Amarelo: protected (exige confirm_protected=True)
        - Vermelho: critical (exige unlock_critical=True, audit_reason e unlocked_by com auditoria)
        - NUNCA altera a Product Bible oficial (Seção 29 e M07-A03).
        """
        layout = self.get_layout(layout_id)
        if not layout:
            raise LayoutValidationError(f"Layout '{layout_id}' não encontrado.")

        # REGRA CRÍTICA: NUNCA ALTERAR A PRODUCT BIBLE AUTOMATICAMENTE (Seção 29 / M07-A03)
        # Qualquer tentativa de submeter 'product_bible' ou alterar ficha de produto pelo editor de layout é sumariamente bloqueada.
        if 'product_bible' in updates or 'official_product_update' in updates or 'bible_version' in updates:
            raise LayoutValidationError(
                "Edição de layout nunca altera a Product Bible oficial automaticamente (Seção 29 / M07-A03)."
            )

        messages = []
        now = self._now()
        audit_records: List[Dict[str, Any]] = []

        # 1. Processa e valida alterações de atributos
        for key, new_val in updates.items():
            level = ATTRIBUTE_CLASSIFICATION.get(key, PROTECTION_FREE)

            # Validação Amarelo (Protected)
            if level == PROTECTION_PROTECTED:
                if not confirm_protected:
                    raise ProtectedAttributeError(
                        f"Atributo protegido '{key}' exige confirmação explícita antes da alteração (Seção 29)."
                    )
                messages.append(f"Atributo protegido '{key}' atualizado mediante confirmação.")

            # Validação Vermelho (Critical)
            elif level == PROTECTION_CRITICAL:
                if not unlock_critical:
                    raise CriticalAttributeLockedError(
                        f"Atributo crítico '{key}' está bloqueado. Exige autorização explícita de unlock e registro de exceção (Seção 29)."
                    )
                clean_reason = (audit_reason or '').strip()
                clean_operator = (unlocked_by or '').strip()
                if not clean_reason or not clean_operator:
                    raise CriticalAttributeLockedError(
                        f"Para desbloquear o atributo crítico '{key}', é obrigatório fornecer justificativa formal e identificação do responsável."
                    )
                # Registra auditoria
                audit_records.append({
                    'id': f"audit-{uuid.uuid4().hex[:12]}",
                    'layout_id': layout.id,
                    'slide_id': layout.slide_id,
                    'attribute_name': key,
                    'protection_level': PROTECTION_CRITICAL,
                    'previous_value': str(self._get_current_attr_value(layout, key)),
                    'new_value': str(new_val),
                    'reason': clean_reason,
                    'operator': clean_operator,
                    'created_at': now,
                })
                messages.append(f"Atributo crítico '{key}' desbloqueado sob exceção registrada: '{clean_reason}' por {clean_operator}.")

        # 2. Aplica as mutações no modelo em memória
        self._apply_updates_to_layout(layout, updates)

        # Valida restrições de domínios
        if layout.image.framing not in VALID_FRAMINGS:
            raise LayoutValidationError(f"Enquadramento inválido: '{layout.image.framing}'. Válidos: {', '.join(VALID_FRAMINGS)}")
        if layout.image.lighting not in VALID_LIGHTINGS:
            raise LayoutValidationError(f"Iluminação inválida: '{layout.image.lighting}'. Válidas: {', '.join(VALID_LIGHTINGS)}")
        if layout.image.scale <= 0.1 or layout.image.scale > 3.0:
            raise LayoutValidationError("Escala da imagem deve ser entre 0.1 e 3.0.")

        # Verifica safe areas para alertar sobreposição/cortes
        warnings = self.engine.validate_safe_zones(layout)
        messages.extend(warnings)

        # 3. Persiste no banco de dados
        layout.updated_at = now
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''UPDATE slide_layouts
                   SET elements_json=?, protection_overrides_json=?, updated_at=?
                   WHERE id=?''',
                (
                    json.dumps(layout.to_dict()['elements'], ensure_ascii=False),
                    json.dumps(layout.protection_overrides, ensure_ascii=False),
                    now,
                    layout.id,
                ),
            )
            for rec in audit_records:
                conn.execute(
                    '''INSERT INTO layout_audit_log (id, layout_id, slide_id, attribute_name, protection_level, previous_value, new_value, reason, operator, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        rec['id'],
                        rec['layout_id'],
                        rec['slide_id'],
                        rec['attribute_name'],
                        rec['protection_level'],
                        rec['previous_value'],
                        rec['new_value'],
                        rec['reason'],
                        rec['operator'],
                        rec['created_at'],
                    ),
                )

        return layout, messages

    def _get_current_attr_value(self, layout: SlideLayout, key: str) -> Any:
        if key == 'logo_locked':
            return layout.logo.aspect_ratio_locked
        if key == 'product_id':
            return getattr(layout.image, 'asset_id', None)
        return layout.protection_overrides.get(key)

    def _apply_updates_to_layout(self, layout: SlideLayout, updates: Dict[str, Any]):
        # Verde (Livre)
        if 'position_x' in updates:
            layout.image.position_x = int(updates['position_x'])
        if 'position_y' in updates:
            layout.image.position_y = int(updates['position_y'])
        if 'scale' in updates:
            layout.image.scale = float(updates['scale'])
        if 'framing' in updates:
            layout.image.framing = str(updates['framing'])
        if 'lighting' in updates:
            layout.image.lighting = str(updates['lighting'])

        # Amarelo (Protected)
        if 'headline_text' in updates:
            layout.headline.text = str(updates['headline_text'])
        if 'cta_text' in updates:
            layout.cta.text = str(updates['cta_text'])
        if 'font_family' in updates:
            layout.headline.font_family = str(updates['font_family'])
        if 'font_size' in updates:
            layout.headline.font_size = int(updates['font_size'])
        if 'headline_color' in updates:
            layout.headline.color = str(updates['headline_color'])
        if 'cta_color' in updates:
            layout.cta.bg_color = str(updates['cta_color'])
        if 'decorative_kind' in updates:
            layout.decorative.kind = str(updates['decorative_kind'])
        if 'decorative_label' in updates:
            layout.decorative.label = str(updates['decorative_label'])

        # Vermelho (Critical)
        if 'logo_locked' in updates:
            layout.logo.aspect_ratio_locked = bool(updates['logo_locked'])
            layout.protection_overrides['logo_locked'] = layout.logo.aspect_ratio_locked
        if 'logo_aspect_ratio' in updates:
            layout.protection_overrides['logo_aspect_ratio'] = float(updates['logo_aspect_ratio'])

    def switch_format(self, layout_id: str, target_format: str) -> SlideLayout:
        """Altera o formato do layout entre 4:5 e 9:16 com adaptação responsiva determinística."""
        layout = self.get_layout(layout_id)
        if not layout:
            raise LayoutValidationError(f"Layout '{layout_id}' não encontrado.")
        if layout.format == target_format:
            return layout

        adapted = self.engine.adapt_format(layout, target_format)
        now = self._now()
        adapted.updated_at = now

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''UPDATE slide_layouts
                   SET format=?, elements_json=?, updated_at=?
                   WHERE id=?''',
                (
                    target_format,
                    json.dumps(adapted.to_dict()['elements'], ensure_ascii=False),
                    now,
                    adapted.id,
                ),
            )
        return adapted

    def approve_layout(self, layout_id: str, approved_by: str) -> SlideLayout:
        """Aprova formalmente uma composição de layout."""
        clean_by = (approved_by or '').strip()
        if not clean_by:
            raise LayoutValidationError("Responsável pela aprovação do layout é obrigatório.")

        layout = self.get_layout(layout_id)
        if not layout:
            raise LayoutValidationError(f"Layout '{layout_id}' não encontrado.")

        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                'UPDATE slide_layouts SET is_approved=1, approved_at=?, approved_by=?, updated_at=? WHERE id=?',
                (now, clean_by, now, layout_id),
            )
        layout.is_approved = True
        layout.approved_at = now
        layout.approved_by = clean_by
        layout.updated_at = now
        return layout

    def list_audit_entries(self, layout_id: Optional[str] = None, slide_id: Optional[str] = None) -> List[LayoutAuditEntry]:
        """Recupera histórico de auditoria de alterações em atributos críticos."""
        query = 'SELECT * FROM layout_audit_log'
        params = []
        conditions = []
        if layout_id:
            conditions.append('layout_id=?')
            params.append(layout_id)
        if slide_id:
            conditions.append('slide_id=?')
            params.append(slide_id)
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        query += ' ORDER BY created_at DESC'

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [LayoutAuditEntry(**dict(r)) for r in rows]

