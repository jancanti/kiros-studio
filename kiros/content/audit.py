"""Auditor Pré-Publicação com Checklist Rigoroso de Governança (Seções 34-38 e M08-A05)."""
from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional

from kiros.content.models import (
    CaptionContent,
    StorySequence,
    AuditCheckItem,
    PrePublishAuditResult,
    EMOJI_PATTERN,
    HASHTAG_PATTERN,
    PROHIBITED_AI_CLICHES,
    PROHIBITED_CTA_FORMULAS,
)
from kiros.content.copy_engine import CopyEngine
from kiros.content.stories_engine import StoriesEngine


class PrePublishAuditor:
    """Validador de checklist pré-publicação para copy, legendas, preços e Stories."""

    def __init__(self, copy_engine: Optional[CopyEngine] = None, stories_engine: Optional[StoriesEngine] = None):
        self.copy_engine = copy_engine or CopyEngine()
        self.stories_engine = stories_engine or StoriesEngine()

    def audit_caption(
        self,
        caption: CaptionContent,
        product_data: Optional[Dict[str, Any]] = None,
        operator: str = 'Operador KIROS',
    ) -> PrePublishAuditResult:
        """Executa auditoria pré-publicação em uma legenda/copy (Seções 34-37)."""
        now = datetime.now(timezone.utc).isoformat()
        checks: List[AuditCheckItem] = []
        blocked_reasons: List[str] = []
        warnings: List[str] = []

        full_text = f"{caption.text} {caption.cta_text}".strip()

        # 1. Checagem de Emojis (Seção 34: proibido em legendas, CTAs, textos editoriais)
        if EMOJI_PATTERN.search(full_text):
            checks.append(AuditCheckItem(
                check_id='no_emojis',
                category='voz_e_estilo',
                title='Ausência de Emojis',
                status='blocked',
                message='Uso de emojis detectado. A voz da KIROS proíbe emojis em legendas, CTAs e textos editoriais (Seção 34).',
                fix_suggestion='Remover emojis da legenda e do CTA.',
            ))
            blocked_reasons.append('Emojis proibidos em legendas e CTAs editoriais.')
        else:
            checks.append(AuditCheckItem(
                check_id='no_emojis',
                category='voz_e_estilo',
                title='Ausência de Emojis',
                status='passed',
                message='Nenhum emoji detectado no texto editorial.',
            ))

        # 2. Checagem de Hashtags Automáticas (Seção 34: não usar hashtags automaticamente)
        if HASHTAG_PATTERN.search(caption.text):
            checks.append(AuditCheckItem(
                check_id='no_auto_hashtags',
                category='voz_e_estilo',
                title='Ausência de Hashtags Automáticas',
                status='blocked',
                message='Hashtags automáticas detectadas. A KIROS não usa hashtags automaticamente (Seção 34).',
                fix_suggestion='Remover hashtags inseridas automaticamente.',
            ))
            blocked_reasons.append('Hashtags automáticas são proibidas.')
        else:
            checks.append(AuditCheckItem(
                check_id='no_auto_hashtags',
                category='voz_e_estilo',
                title='Ausência de Hashtags Automáticas',
                status='passed',
                message='Texto limpo sem hashtags automáticas.',
            ))

        # 3. Checagem de Clichês de IA (Seção 34: evitar clichês e linguagem corporativa)
        lower_text = full_text.lower()
        found_cliches = [c for c in PROHIBITED_AI_CLICHES if c in lower_text]
        if found_cliches:
            msg = f"Clichê(s) de IA detectado(s): {', '.join(found_cliches)}. Voz deve ser brasileira, relaxada e natural (Seção 34)."
            checks.append(AuditCheckItem(
                check_id='voice_cliches',
                category='voz_e_estilo',
                title='Voz Natural Brasileira (Anti-Clichês)',
                status='blocked',
                message=msg,
                fix_suggestion='Substituir clichês artificiais de IA por linguagem cotidiana brasileira e elegante.',
            ))
            blocked_reasons.append(f'Clichês de IA proibidos: {", ".join(found_cliches)}')
        else:
            checks.append(AuditCheckItem(
                check_id='voice_cliches',
                category='voz_e_estilo',
                title='Voz Natural Brasileira (Anti-Clichês)',
                status='passed',
                message='Texto sem clichês de IA, alinhado à voz brasileira e relaxada da KIROS.',
            ))

        # 4. Checagem de Fórmulas Artificiais de CTA (Seções 34 e 36)
        found_cta_formulas = [f for f in PROHIBITED_CTA_FORMULAS if f in lower_text]
        if found_cta_formulas:
            msg = f"Fórmula artificial de CTA detectada: {', '.join(found_cta_formulas)} (Seção 36)."
            checks.append(AuditCheckItem(
                check_id='cta_authenticity',
                category='cta',
                title='Autenticidade do CTA',
                status='blocked',
                message=msg,
                fix_suggestion='Remover apelos forçados de engajamento artificial (ex: "comente EU QUERO").',
            ))
            blocked_reasons.append('Fórmulas artificiais de engajamento são proibidas em CTAs.')
        else:
            checks.append(AuditCheckItem(
                check_id='cta_authenticity',
                category='cta',
                title='Autenticidade do CTA',
                status='passed',
                message='CTA sutil, contextual ou ausente, sem pedidos forçados de comentários.',
            ))

        # 5. Governança de Preço e Invenção Comercial (Seções 35 e 37)
        fabrication_issues = self.copy_engine.detect_commercial_fabrication(
            full_text,
            allowed_price=caption.price_value if caption.show_price else None,
        )
        if fabrication_issues:
            checks.append(AuditCheckItem(
                check_id='no_commercial_fabrication',
                category='verdade_comercial',
                title='Verdade Comercial e Anti-Invenção',
                status='blocked',
                message="; ".join(fabrication_issues),
                fix_suggestion='Remover menções a promoções inventadas, escassez fictícia ou preços não autorizados.',
            ))
            blocked_reasons.extend(fabrication_issues)
        else:
            checks.append(AuditCheckItem(
                check_id='no_commercial_fabrication',
                category='verdade_comercial',
                title='Verdade Comercial e Anti-Invenção',
                status='passed',
                message='Nenhuma invenção de estoque, promoção ou dado comercial detectada.',
            ))

        # 6. Validação de Exibição de Preço (Seção 37: não mostrar por padrão; se mostrar, explicar e aprovar)
        if caption.show_price:
            price_issues = []
            if not caption.price_value:
                price_issues.append('Preço solicitado para exibição mas sem valor definido.')
            if not caption.price_justification or not caption.price_justification.strip():
                price_issues.append('Exibição de preço sem justificativa estratégica documentada.')
            if not caption.price_approved_by or not caption.price_approved_by.strip():
                price_issues.append('Exibição de preço sem aprovação explícita de operador.')

            if price_issues:
                checks.append(AuditCheckItem(
                    check_id='price_governance',
                    category='preco_e_site',
                    title='Governança de Exibição de Preço',
                    status='blocked',
                    message="; ".join(price_issues),
                    fix_suggestion='Preencher justificativa estratégica e obter aprovação explícita de operador para mostrar preço.',
                ))
                blocked_reasons.extend(price_issues)
            else:
                checks.append(AuditCheckItem(
                    check_id='price_governance',
                    category='preco_e_site',
                    title='Governança de Exibição de Preço',
                    status='passed',
                    message=f'Exibição de preço aprovada por {caption.price_approved_by} com justificativa: "{caption.price_justification}".',
                ))
        else:
            checks.append(AuditCheckItem(
                check_id='price_governance',
                category='preco_e_site',
                title='Governança de Exibição de Preço',
                status='passed',
                message='Preço oculto por padrão (Seção 37).',
            ))

        # 7. Direcionamento para Link da Bio ou URL de Destino (Seção 37)
        if caption.destination_url or 'link da bio' in lower_text or 'link na bio' in lower_text or caption.cta_mode == 'none':
            checks.append(AuditCheckItem(
                check_id='destination_configured',
                category='preco_e_site',
                title='Página de Destino / Link da Bio',
                status='passed',
                message='Priorização de link da bio ou URL de destino configurada sem dependência profunda.',
            ))
        else:
            warnings.append('Nenhum link da bio ou URL de destino configurado no CTA ou legenda.')
            checks.append(AuditCheckItem(
                check_id='destination_configured',
                category='preco_e_site',
                title='Página de Destino / Link da Bio',
                status='warning',
                message='Recomendado mencionar o link da bio ou configurar página de destino para o público encontrar o produto.',
                fix_suggestion='Adicionar menção suave ao link da bio.',
            ))

        is_ready = len(blocked_reasons) == 0

        return PrePublishAuditResult(
            target_type='slide_copy',
            target_id=caption.slide_id or caption.id,
            is_ready=is_ready,
            checks=checks,
            blocked_reasons=blocked_reasons,
            warnings=warnings,
            operator=operator,
            created_at=now,
        )

    def audit_story_sequence(
        self,
        sequence: StorySequence,
        operator: str = 'Operador KIROS',
    ) -> PrePublishAuditResult:
        """Executa auditoria pré-publicação em uma sequência de Stories (Seção 38)."""
        now = datetime.now(timezone.utc).isoformat()
        checks: List[AuditCheckItem] = []
        blocked_reasons: List[str] = []
        warnings: List[str] = []

        # 1. Não simplesmente redimensionar feed: exige planejamento de sequência (mínimo 3 frames)
        if len(sequence.frames) < 3:
            msg = (
                f"Sequência possui apenas {len(sequence.frames)} frame(s). "
                "Stories não são mero redimensionamento do feed; exigem planejamento de sequência com no mínimo 3 frames (Seção 38)."
            )
            checks.append(AuditCheckItem(
                check_id='story_sequence_planning',
                category='estrutura_stories',
                title='Planejamento de Sequência Narrativa',
                status='blocked',
                message=msg,
                fix_suggestion='Planejar sequência completa de 3 a 5 frames com papéis narrativos (gancho, contexto, sensorial, interação, fechamento).',
            ))
            blocked_reasons.append('Stories exigem planejamento de sequência próprio (mínimo 3 frames).')
        else:
            checks.append(AuditCheckItem(
                check_id='story_sequence_planning',
                category='estrutura_stories',
                title='Planejamento de Sequência Narrativa',
                status='passed',
                message=f'Sequência de Stories bem estruturada com {len(sequence.frames)} frames narrativos.',
            ))

        # 2. Presença de Papéis Narrativos Essenciais
        roles = [f.narrative_role for f in sequence.frames]
        if 'hook' not in roles:
            checks.append(AuditCheckItem(
                check_id='story_narrative_roles',
                category='estrutura_stories',
                title='Presença de Gancho de Abertura',
                status='warning',
                message='Recomendado incluir um frame inicial com papel de gancho visual (hook) para engajamento.',
                fix_suggestion='Definir o primeiro frame com papel narrative_role="hook".',
            ))
            warnings.append('Sequência sem frame inicial de gancho visual explícito.')
        else:
            checks.append(AuditCheckItem(
                check_id='story_narrative_roles',
                category='estrutura_stories',
                title='Presença de Gancho de Abertura',
                status='passed',
                message='Gancho de abertura presente no primeiro frame.',
            ))

        # 3. Interações Apenas Quando Fizer Sentido e com Justificativa Contextual (Seção 38)
        unjustified_interactions = [
            f.frame_order for f in sequence.frames
            if f.interaction_type != 'none' and not f.interaction_justification.strip()
        ]
        if unjustified_interactions:
            msg = f"Frames {unjustified_interactions} possuem interação ({[f.interaction_type for f in sequence.frames if f.frame_order in unjustified_interactions]}) sem justificativa contextual. Usar interações somente quando fizer sentido (Seção 38)."
            checks.append(AuditCheckItem(
                check_id='story_interaction_justification',
                category='interacoes_stories',
                title='Justificativa de Interação Contextual',
                status='blocked',
                message=msg,
                fix_suggestion='Fornecer justificativa contextual para cada elemento interativo (enquete, caixinha, etc.).',
            ))
            blocked_reasons.append('Interações em Stories exigem justificativa contextual explícita.')
        else:
            checks.append(AuditCheckItem(
                check_id='story_interaction_justification',
                category='interacoes_stories',
                title='Justificativa de Interação Contextual',
                status='passed',
                message='Todas as interações utilizadas possuem justificativa contextual alinhada à estratégia.',
            ))

        # 4. Checagem de Emojis nos Textos de Tela dos Stories (Seção 34)
        all_overlay_text = " ".join(f.overlay_text for f in sequence.frames)
        if EMOJI_PATTERN.search(all_overlay_text):
            checks.append(AuditCheckItem(
                check_id='story_emojis',
                category='voz_e_estilo',
                title='Ausência de Emojis em Textos de Tela',
                status='blocked',
                message='Emojis detectados no texto de tela dos Stories. Proibido em textos editoriais da KIROS (Seção 34).',
                fix_suggestion='Remover emojis dos textos de tela.',
            ))
            blocked_reasons.append('Emojis proibidos em textos de tela de Stories.')
        else:
            checks.append(AuditCheckItem(
                check_id='story_emojis',
                category='voz_e_estilo',
                title='Ausência de Emojis em Textos de Tela',
                status='passed',
                message='Textos de tela limpos sem emojis.',
            ))

        is_ready = len(blocked_reasons) == 0

        return PrePublishAuditResult(
            target_type='story_sequence',
            target_id=sequence.id,
            is_ready=is_ready,
            checks=checks,
            blocked_reasons=blocked_reasons,
            warnings=warnings,
            operator=operator,
            created_at=now,
        )

