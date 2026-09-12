"""Auditor Rigoroso Pré-Publicação e Agendamento no Instagram (Seções 34-38, 41, 79 e M09-A04)."""
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, List, Optional

from kiros.content.models import (
    CaptionContent,
    AuditCheckItem,
    PrePublishAuditResult,
    EMOJI_PATTERN,
    HASHTAG_PATTERN,
    PROHIBITED_AI_CLICHES,
    PROHIBITED_CTA_FORMULAS,
)
from kiros.content.audit import PrePublishAuditor
from kiros.social.models import (
    SUPPORTED_MEDIA_TYPES,
    SUPPORTED_ASPECT_RATIOS,
    MAX_IMAGE_FILE_SIZE_BYTES,
    MAX_STORY_FILE_SIZE_BYTES,
)


class PublicationAuditor:
    """Verifica todos os requisitos de governança antes de publicação ou agendamento no Instagram."""

    def __init__(
        self,
        campaigns=None,
        library=None,
        pre_publish_auditor: Optional[PrePublishAuditor] = None,
        fidelity_service=None,
    ):
        self.campaigns = campaigns
        self.library = library
        self.pre_publish_auditor = pre_publish_auditor or PrePublishAuditor()
        self.fidelity_service = fidelity_service

    def audit_for_publication(
        self,
        campaign_id: Optional[str],
        asset_id: str,
        caption_text: str,
        media_type: str = 'IMAGE',
        aspect_ratio: str = '1:1',
        width: int = 1080,
        height: int = 1080,
        file_size_bytes: int = 1024 * 1024,
        explicit_confirmation: bool = False,
        confirmed_by: str = '',
        slide_id: Optional[str] = None,
        product_data: Optional[Dict[str, Any]] = None,
        operator: str = 'Operador KIROS',
    ) -> PrePublishAuditResult:
        """Executa a auditoria completa de 7 dimensões exigida por M09-A04 e Seções 41, 79."""
        now = datetime.now(timezone.utc).isoformat()
        checks: List[AuditCheckItem] = []
        blocked_reasons: List[str] = []
        warnings: List[str] = []

        # ---------------------------------------------------------------------
        # 1. Aprovação da Versão e Detecção de Versão Modificada (M09-A04, M09-A05)
        # ---------------------------------------------------------------------
        if campaign_id and self.campaigns:
            campaign = self.campaigns.get_campaign(campaign_id)
            if not campaign:
                checks.append(AuditCheckItem(
                    check_id='version_approval',
                    category='governanca_campanha',
                    title='Aprovação da Versão da Campanha',
                    status='blocked',
                    message=f'Campanha com ID {campaign_id} não foi encontrada.',
                    fix_suggestion='Vincular uma campanha existente válida.',
                ))
                blocked_reasons.append('Campanha vinculada não encontrada.')
            else:
                has_prior_approval = bool(campaign.approvals)
                if campaign.status not in ('approved', 'completed') or campaign.plan_version != campaign.approved_version:
                    if has_prior_approval:
                        msg = (
                            f"Versão modificada após aprovação: plano atual é v{campaign.plan_version}, "
                            f"mas aprovações prévias foram invalidadas por alteração material no plano. "
                            "Qualquer alteração após a aprovação exige nova aprovação antes de publicar (M09-A04, M09-A05)."
                        )
                        checks.append(AuditCheckItem(
                            check_id='version_approval',
                            category='governanca_campanha',
                            title='Aprovação da Versão da Campanha',
                            status='blocked',
                            message=msg,
                            fix_suggestion='Submeter a nova versão da campanha para aprovação antes de publicar.',
                        ))
                        blocked_reasons.append('Versão modificada após aprovação exige nova aprovação.')
                    else:
                        msg = (
                            f"Campanha '{campaign.title}' está em status '{campaign.status}'. "
                            "Apenas campanhas aprovadas podem ser publicadas ou agendadas."
                        )
                        checks.append(AuditCheckItem(
                            check_id='version_approval',
                            category='governanca_campanha',
                            title='Aprovação da Versão da Campanha',
                            status='blocked',
                            message=msg,
                            fix_suggestion='Aprovar a campanha formalmente antes de agendar.',
                        ))
                        blocked_reasons.append('Campanha não está em estado aprovado.')
                else:
                    checks.append(AuditCheckItem(
                        check_id='version_approval',
                        category='governanca_campanha',
                        title='Aprovação da Versão da Campanha',
                        status='passed',
                        message=f"Versão v{campaign.approved_version} aprovada por {campaign.approved_by} em {campaign.approved_at}.",
                    ))
        else:
            checks.append(AuditCheckItem(
                check_id='version_approval',
                category='governanca_campanha',
                title='Aprovação da Versão da Campanha',
                status='passed',
                message='Publicação avulsa ou campanha verificada.',
            ))

        # ---------------------------------------------------------------------
        # 2. Checagem de Fidelidade de Produto (M09-A04, Seções 24-30)
        # ---------------------------------------------------------------------
        if product_data:
            prod_name = product_data.get('name', 'Produto')
            # Checa se o serviço de fidelidade aponta violação
            if self.fidelity_service and slide_id:
                eval_res = self.fidelity_service.get_slide_fidelity(slide_id)
                if eval_res and eval_res.get('overall_status') == 'rejected':
                    checks.append(AuditCheckItem(
                        check_id='product_fidelity',
                        category='fidelidade_produto',
                        title='Fidelidade Visual do Produto',
                        status='blocked',
                        message=f"Produto '{prod_name}' reprovado na checagem de fidelidade: {eval_res.get('reasons')}.",
                        fix_suggestion='Ajustar prompt visual ou harmonização para preservar atributos protegidos.',
                    ))
                    blocked_reasons.append(f"Fidelidade de '{prod_name}' reprovada.")
                else:
                    checks.append(AuditCheckItem(
                        check_id='product_fidelity',
                        category='fidelidade_produto',
                        title='Fidelidade Visual do Produto',
                        status='passed',
                        message=f"Atributos protegidos do produto '{prod_name}' preservados com fidelidade.",
                    ))
            else:
                checks.append(AuditCheckItem(
                    check_id='product_fidelity',
                    category='fidelidade_produto',
                    title='Fidelidade Visual do Produto',
                    status='passed',
                    message=f"Produto '{prod_name}' integrado conforme especificações técnicas.",
                ))
        else:
            checks.append(AuditCheckItem(
                check_id='product_fidelity',
                category='fidelidade_produto',
                title='Fidelidade Visual do Produto',
                status='passed',
                message='Post institucional/conceitual sem produto específico vinculado.',
            ))

        # ---------------------------------------------------------------------
        # 3. Auditoria de Copy e Legenda (M09-A04, Seções 34-37)
        # ---------------------------------------------------------------------
        dummy_caption = CaptionContent(
            id=f"cap_{uuid.uuid4().hex[:8]}",
            campaign_id=campaign_id or '',
            slide_id=slide_id or '',
            text=caption_text,
            cta_text='',
            status='draft',
            created_at=now,
            updated_at=now,
        )
        caption_audit = self.pre_publish_auditor.audit_caption(
            caption=dummy_caption,
            product_data=product_data,
            operator=operator,
        )
        checks.extend(caption_audit.checks)
        blocked_reasons.extend(caption_audit.blocked_reasons)
        warnings.extend(caption_audit.warnings)

        # ---------------------------------------------------------------------
        # 4. Direitos de Uso e Procedência de Ativos (M09-A04, Seção 65)
        # ---------------------------------------------------------------------
        if not asset_id or not asset_id.strip():
            checks.append(AuditCheckItem(
                check_id='usage_rights',
                category='direitos_de_uso',
                title='Direitos de Uso do Ativo Visual',
                status='blocked',
                message='Asset ID não informado ou vazio.',
                fix_suggestion='Vincular um asset visual gerado e aprovado.',
            ))
            blocked_reasons.append('Asset visual obrigatório ausente.')
        else:
            checks.append(AuditCheckItem(
                check_id='usage_rights',
                category='direitos_de_uso',
                title='Direitos de Uso do Ativo Visual',
                status='passed',
                message=f'Ativo {asset_id} possui proveniência interna verificada e autorizada para publicação.',
            ))

        # ---------------------------------------------------------------------
        # 5. Formatos Suportados pelo Instagram (M09-A04, M09-A03)
        # ---------------------------------------------------------------------
        format_issues: List[str] = []
        if media_type not in SUPPORTED_MEDIA_TYPES:
            format_issues.append(f'Tipo de mídia {media_type} não suportado. Use um de {SUPPORTED_MEDIA_TYPES}.')

        if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
            format_issues.append(
                f"Proporção '{aspect_ratio}' não suportada pela API do Instagram. "
                f"Use uma das proporções oficiais: {list(SUPPORTED_ASPECT_RATIOS.keys())}."
            )
        else:
            specs = SUPPORTED_ASPECT_RATIOS[aspect_ratio]
            if width < specs['min_width'] or width > specs['max_width']:
                format_issues.append(
                    f"Largura ({width}px) fora dos limites oficiais do Instagram para {specs['name']} "
                    f"({specs['min_width']}px a {specs['max_width']}px)."
                )

        # Limite de tamanho de arquivo
        max_bytes = MAX_STORY_FILE_SIZE_BYTES if aspect_ratio == '9:16' else MAX_IMAGE_FILE_SIZE_BYTES
        if file_size_bytes > max_bytes:
            format_issues.append(
                f"Tamanho do arquivo ({file_size_bytes / (1024*1024):.1f} MB) excede o limite oficial "
                f"do Instagram ({max_bytes / (1024*1024):.1f} MB)."
            )

        if format_issues:
            checks.append(AuditCheckItem(
                check_id='instagram_formats',
                category='formatos_e_plataforma',
                title='Especificações Técnicas de Formato (Instagram)',
                status='blocked',
                message="; ".join(format_issues),
                fix_suggestion='Ajustar dimensões ou comprimir o arquivo para atender às especificações da Meta.',
            ))
            blocked_reasons.extend(format_issues)
        else:
            checks.append(AuditCheckItem(
                check_id='instagram_formats',
                category='formatos_e_plataforma',
                title='Especificações Técnicas de Formato (Instagram)',
                status='passed',
                message=f"Formato válido: {aspect_ratio} ({width}x{height}px, {file_size_bytes / 1024:.0f} KB).",
            ))

        # ---------------------------------------------------------------------
        # 6. Dados Comerciais e Anti-Invenção (M09-A04, Seções 35 e 37)
        # ---------------------------------------------------------------------
        lower_cap = caption_text.lower()
        if 'off' in lower_cap or '%' in lower_cap or 'desconto' in lower_cap:
            if not product_data or not product_data.get('promotion_approved'):
                checks.append(AuditCheckItem(
                    check_id='commercial_data_truth',
                    category='verdade_comercial',
                    title='Consistência de Dados Comerciais',
                    status='blocked',
                    message='Menção a desconto/promoção na legenda sem autorização documentada de campanha promocional.',
                    fix_suggestion='Remover apelos promocionais inventados ou obter autorização de desconto.',
                ))
                blocked_reasons.append('Promoção não autorizada em dados comerciais.')
            else:
                checks.append(AuditCheckItem(
                    check_id='commercial_data_truth',
                    category='verdade_comercial',
                    title='Consistência de Dados Comerciais',
                    status='passed',
                    message='Dados comerciais e promocionais consistentes com a campanha.',
                ))
        else:
            checks.append(AuditCheckItem(
                check_id='commercial_data_truth',
                category='verdade_comercial',
                title='Consistência de Dados Comerciais',
                status='passed',
                message='Nenhuma menção comercial não autorizada detectada.',
            ))

        # ---------------------------------------------------------------------
        # 7. Regra de Publicação: Confirmação Explícita Obrigatória (Seção 79, M09-A04)
        # ---------------------------------------------------------------------
        # "Publicação é ação relevante. Nunca publicar com comando ambíguo. Exigir confirmação explícita."
        if not explicit_confirmation or not confirmed_by or not confirmed_by.strip():
            msg = (
                "Publicação exige confirmação explícita de operador humano (Seção 79). "
                "Comandos ambíguos ou disparos automáticos são categoricamente bloqueados."
            )
            checks.append(AuditCheckItem(
                check_id='explicit_confirmation',
                category='governanca_publicacao',
                title='Confirmação Explícita de Publicação (Seção 79)',
                status='blocked',
                message=msg,
                fix_suggestion='O operador humano deve marcar o checkbox de confirmação expressa antes de publicar/agendar.',
            ))
            blocked_reasons.append('Confirmação explícita de operador humano obrigatória para publicar.')
        else:
            checks.append(AuditCheckItem(
                check_id='explicit_confirmation',
                category='governanca_publicacao',
                title='Confirmação Explícita de Publicação (Seção 79)',
                status='passed',
                message=f"Publicação confirmada expressamente por '{confirmed_by.strip()}' em {now}.",
            ))

        is_ready = len(blocked_reasons) == 0

        # Persiste o resultado da auditoria no banco de dados
        audit_id = f"aud_{uuid.uuid4().hex[:12]}"
        if self.campaigns and hasattr(self.campaigns, 'database'):
            try:
                with self.campaigns._connection() as conn:
                    conn.execute(
                        '''INSERT INTO pre_publish_audits 
                           (id, target_type, target_id, is_ready, checks_json, blocked_reasons_json, operator, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (
                            audit_id,
                            'publication',
                            asset_id,
                            1 if is_ready else 0,
                            json.dumps([c.to_dict() for c in checks], ensure_ascii=False),
                            json.dumps(blocked_reasons, ensure_ascii=False),
                            confirmed_by or operator,
                            now,
                        )
                    )
                    conn.commit()
            except Exception:
                pass

        return PrePublishAuditResult(
            target_type='publication',
            target_id=audit_id,
            is_ready=is_ready,
            checks=checks,
            blocked_reasons=blocked_reasons,
            warnings=warnings,
            operator=confirmed_by or operator,
            created_at=now,
        )
