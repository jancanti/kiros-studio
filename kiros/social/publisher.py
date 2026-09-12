"""Implementação operacional do SocialPublisher para Instagram (Seções 41, 68, 69, 70, 79 e M09-A03, M09-A05, M09-A06)."""
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from kiros.core.contracts import SocialPublisher
from kiros.infrastructure.security import ExternalGateway
from kiros.social.models import (
    SocialPublication,
    AccountStatus,
    INSTAGRAM_PERMISSIONS,
    MAX_POSTS_PER_24_HOURS,
    MIN_SCHEDULE_AHEAD_SECONDS,
    MAX_SCHEDULE_AHEAD_SECONDS,
)
from kiros.social.audit import PublicationAuditor


class InstagramAPIError(RuntimeError):
    """Erro estruturado de falha de API seguindo a Seção 69 da especificação."""

    def __init__(self, provider: str, stage: str, cause: str, suggested_fix: str, status_code: int = 500):
        self.provider = provider
        self.stage = stage
        self.cause = cause
        self.suggested_fix = suggested_fix
        self.status_code = status_code
        super().__init__(f"[{provider} - {stage}] {cause}. Sugestão: {suggested_fix}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'provider': self.provider,
            'stage': self.stage,
            'cause': self.cause,
            'suggested_fix': self.suggested_fix,
            'status_code': self.status_code,
        }


class InstagramPublisher(SocialPublisher):
    """Implementa o fluxo operacional oficial de publicação e agendamento da Meta Instagram Graph API."""

    def __init__(
        self,
        database,
        gateway: ExternalGateway,
        auditor: Optional[PublicationAuditor] = None,
        mock_mode: bool = True,
    ):
        self.database = database
        self.gateway = gateway
        self.auditor = auditor or PublicationAuditor()
        self.mock_mode = mock_mode

        # Estado da simulação determinística de erros para testes
        self.simulate_service_unavailable: bool = False
        self.simulate_rate_limit: bool = False
        self.simulate_timeout: bool = False

    def _connection(self):
        conn = sqlite3.connect(self.database.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_account_status(self) -> AccountStatus:
        """Obtém status da conta oficial e limites de publicação disponíveis."""
        now = self._now_iso()
        with self._connection() as conn:
            row = conn.execute('SELECT * FROM instagram_accounts WHERE id="default"').fetchone()
            if not row:
                status = AccountStatus(
                    id='default',
                    account_id='mock_ig_kiros_business_12345',
                    username='kiros.aromas',
                    account_type='business',
                    connection_status='mock' if self.mock_mode else 'unvalidated',
                    permissions=list(INSTAGRAM_PERMISSIONS),
                    rate_limit_total=MAX_POSTS_PER_24_HOURS,
                    rate_limit_remaining=MAX_POSTS_PER_24_HOURS,
                    last_checked_at=now,
                    updated_at=now,
                )
                conn.execute(
                    '''INSERT INTO instagram_accounts 
                       (id, account_id, username, account_type, connection_status, permissions_json, 
                        rate_limit_total, rate_limit_remaining, last_checked_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        status.id,
                        status.account_id,
                        status.username,
                        status.account_type,
                        status.connection_status,
                        json.dumps(status.permissions),
                        status.rate_limit_total,
                        status.rate_limit_remaining,
                        status.last_checked_at,
                        status.updated_at,
                    )
                )
                conn.commit()
                return status

            return AccountStatus(
                id=row['id'],
                account_id=row['account_id'],
                username=row['username'],
                account_type=row['account_type'],
                connection_status=row['connection_status'],
                permissions=json.loads(row['permissions_json'] or '[]'),
                rate_limit_total=row['rate_limit_total'],
                rate_limit_remaining=row['rate_limit_remaining'],
                last_checked_at=row['last_checked_at'],
                updated_at=row['updated_at'],
            )

    def publish(
        self,
        asset_id: str,
        caption: str,
        campaign_id: Optional[str] = None,
        slide_id: Optional[str] = None,
        calendar_entry_id: Optional[str] = None,
        media_type: str = 'IMAGE',
        aspect_ratio: str = '1:1',
        scheduled_time_iso: Optional[str] = None,
        explicit_confirmation: bool = False,
        confirmed_by: str = '',
        idempotency_key: Optional[str] = None,
    ) -> str:
        """Executa ou agenda uma publicação no Instagram com governança completa."""
        # 1. Regra de Publicação: Confirmação Explícita Obrigatória (Seção 79, M09-A04)
        if not explicit_confirmation or not confirmed_by or not confirmed_by.strip():
            raise PermissionError(
                'Publicação exige confirmação explícita de operador humano (Seção 79). '
                'Comandos ambíguos não autorizam publicação.'
            )

        # 2. Validação de Timezone e Janela de Agendamento (M09-A05)
        scheduled_epoch: Optional[int] = None
        if scheduled_time_iso:
            try:
                sched_dt = datetime.fromisoformat(scheduled_time_iso)
            except ValueError as exc:
                raise ValueError(f'Formato de data inválido para agendamento: {exc}')

            if sched_dt.tzinfo is None:
                raise ValueError(
                    'Data de agendamento deve incluir fuso horário explícito (timezone-aware ISO 8601). '
                    'Datas sem timezone são rejeitadas por segurança operacional.'
                )

            # Converte para UTC
            sched_utc = sched_dt.astimezone(timezone.utc)
            now_utc = datetime.now(timezone.utc)
            diff_seconds = (sched_utc - now_utc).total_seconds()

            if diff_seconds < MIN_SCHEDULE_AHEAD_SECONDS:
                raise ValueError(
                    f'Agendamento deve ser de no mínimo 15 minutos ({MIN_SCHEDULE_AHEAD_SECONDS}s) no futuro. '
                    f'Diferença atual: {diff_seconds:.0f}s.'
                )
            if diff_seconds > MAX_SCHEDULE_AHEAD_SECONDS:
                raise ValueError(
                    f'Agendamento não pode exceder o limite oficial da Meta de 75 dias '
                    f'({MAX_SCHEDULE_AHEAD_SECONDS}s). Diferença atual: {diff_seconds:.0f}s.'
                )
            scheduled_epoch = int(sched_utc.timestamp())

        # 3. Idempotência e Reconciliação (Seção 68, M09-A05)
        if not idempotency_key:
            target = scheduled_time_iso or 'immediate'
            raw_key = f"{campaign_id or 'none'}:{slide_id or asset_id}:{hashlib.sha256(caption.encode()).hexdigest()[:16]}:{target}"
            idempotency_key = f"idem_{hashlib.sha256(raw_key.encode()).hexdigest()[:24]}"

        # Checa se já existe publicação com a mesma chave
        with self._connection() as conn:
            existing = conn.execute(
                'SELECT * FROM social_publications WHERE idempotency_key = ?',
                (idempotency_key,)
            ).fetchone()

            if existing:
                if existing['status'] == 'published':
                    # Reconciliação imediata: nunca publicar duplicado (Seção 68)
                    return existing['external_post_id'] or existing['id']
                elif existing['status'] == 'publishing':
                    return existing['external_container_id'] or existing['id']

        # 4. Auditoria Pré-Publicação (M09-A04)
        audit_res = self.auditor.audit_for_publication(
            campaign_id=campaign_id,
            asset_id=asset_id,
            caption_text=caption,
            media_type=media_type,
            aspect_ratio=aspect_ratio,
            explicit_confirmation=explicit_confirmation,
            confirmed_by=confirmed_by,
            slide_id=slide_id,
        )

        if not audit_res.is_ready:
            raise PermissionError(
                f"Auditoria pré-publicação bloqueou a operação: {'; '.join(audit_res.blocked_reasons)}"
            )

        # 5. Registro Inicial da Publicação
        pub_id = f"pub_{uuid.uuid4().hex[:12]}"
        now = self._now_iso()

        with self._connection() as conn:
            conn.execute(
                '''INSERT INTO social_publications 
                   (id, calendar_entry_id, campaign_id, asset_id, caption, media_type, idempotency_key, 
                    status, provider, external_container_id, external_post_id, explicit_confirmed_by, 
                    explicit_confirmed_at, audit_id, scheduled_publish_time, error_message, 
                    published_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'publishing', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(idempotency_key) DO UPDATE SET 
                   status = 'publishing', updated_at = excluded.updated_at''',
                (
                    pub_id,
                    calendar_entry_id,
                    campaign_id,
                    asset_id,
                    caption,
                    media_type,
                    idempotency_key,
                    'mock' if self.mock_mode else 'instagram',
                    None,
                    None,
                    confirmed_by,
                    now,
                    audit_res.target_id,
                    scheduled_time_iso,
                    None,
                    None,
                    now,
                    now,
                )
            )
            conn.commit()

        # 6. Execução do Fluxo Operacional da Meta
        try:
            external_post_id = self._execute_meta_workflow(
                asset_id=asset_id,
                caption=caption,
                media_type=media_type,
                scheduled_epoch=scheduled_epoch,
                pub_id=pub_id,
            )

            # Sucesso
            with self._connection() as conn:
                conn.execute(
                    '''UPDATE social_publications SET 
                       status = 'published',
                       external_post_id = ?,
                       published_at = ?,
                       updated_at = ?
                       WHERE id = ?''',
                    (external_post_id, self._now_iso(), self._now_iso(), pub_id)
                )
                # Atualiza também a entrada de calendário correspondente, se houver
                if calendar_entry_id:
                    conn.execute(
                        '''UPDATE calendar_entries SET status = 'published', updated_at = ? WHERE id = ?''',
                        (self._now_iso(), calendar_entry_id)
                    )
                conn.commit()

            return external_post_id

        except InstagramAPIError as err:
            with self._connection() as conn:
                conn.execute(
                    '''UPDATE social_publications SET 
                       status = 'failed',
                       error_message = ?,
                       updated_at = ?
                       WHERE id = ?''',
                    (str(err), self._now_iso(), pub_id)
                )
                if calendar_entry_id:
                    conn.execute(
                        '''UPDATE calendar_entries SET status = 'failed', updated_at = ? WHERE id = ?''',
                        (self._now_iso(), calendar_entry_id)
                    )
                conn.commit()
            raise err

    def _execute_meta_workflow(
        self,
        asset_id: str,
        caption: str,
        media_type: str,
        scheduled_epoch: Optional[int],
        pub_id: str,
    ) -> str:
        """Executa as etapas oficiais de publicação suportadas pela documentação da Meta."""
        # Se estamos em modo mock ou sem autorização externa, o gateway protege
        if self.gateway.policy.mode == 'mock' or not self.gateway.policy.allow_publish:
            return self._execute_mock_meta_workflow(asset_id, caption, media_type, scheduled_epoch, pub_id)

        # Em modo live autorizado:
        def live_operation():
            # Etapa 1: Container Creation
            # POST https://graph.facebook.com/v20.0/{ig_user_id}/media
            # Etapa 2: Container Status Polling
            # GET https://graph.facebook.com/v20.0/{container_id}?fields=status_code
            # Etapa 3: Media Publish
            # POST https://graph.facebook.com/v20.0/{ig_user_id}/media_publish
            raise NotImplementedError('Credencial real da Meta Graph API pendente de configuração.')

        return self.gateway.call(live_operation, paid=False, publish=True, approved=True)

    def _execute_mock_meta_workflow(
        self,
        asset_id: str,
        caption: str,
        media_type: str,
        scheduled_epoch: Optional[int],
        pub_id: str,
    ) -> str:
        """Simulação determinística do fluxo operacional da Meta Graph API (M09-A05, M09-A06)."""
        # 1. Simulação de Falhas Controladas (Seção 69, M09-A05)
        if self.simulate_service_unavailable:
            raise InstagramAPIError(
                provider='meta_instagram_graph_api',
                stage='create_media_container',
                cause='Serviço da Meta Graph API temporariamente indisponível (HTTP 503)',
                suggested_fix='Aguardar estabilização dos servidores da Meta e tentar novamente sem perda de dados.',
                status_code=503,
            )

        if self.simulate_rate_limit:
            raise InstagramAPIError(
                provider='meta_instagram_graph_api',
                stage='create_media_container',
                cause='Limite de 25 publicações por 24 horas atingido para esta conta comercial (HTTP 429)',
                suggested_fix='Aguardar renovação da janela móvel de 24 horas antes de enviar novas publicações.',
                status_code=429,
            )

        if self.simulate_timeout:
            raise InstagramAPIError(
                provider='meta_instagram_graph_api',
                stage='wait_container_ready',
                cause='Timeout na transcodificação do container de mídia pela Meta Graph API',
                suggested_fix='Repetir o agendamento; a idempotência garante que não haverá duplicidade.',
                status_code=504,
            )

        # 2. Etapa 1: Criação do Container de Mídia (POST /{ig-user-id}/media)
        container_id = f"cnt_meta_{uuid.uuid4().hex[:14]}"
        with self._connection() as conn:
            conn.execute(
                'UPDATE social_publications SET external_container_id = ?, updated_at = ? WHERE id = ?',
                (container_id, self._now_iso(), pub_id)
            )
            conn.commit()

        # 3. Etapa 2: Status do Container (GET /{container-id}?fields=status_code)
        # No mock, o container fica imediatamente pronto
        container_status = 'FINISHED'

        # 4. Etapa 3: Publicação do Container (POST /{ig-user-id}/media_publish)
        if scheduled_epoch:
            # Post agendado na Meta: retorna o ID do container agendado
            post_id = f"ig_scheduled_{container_id}"
        else:
            # Publicação imediata: gera o post ID definitivo
            post_id = f"ig_post_{uuid.uuid4().hex[:16]}"

        return post_id


class MockSocialPublisher(SocialPublisher):
    """Fixture determinística de SocialPublisher para testes isolados e desenvolvimento seguro."""

    def __init__(self):
        self.published_items: List[Dict[str, Any]] = []

    def publish(self, asset_id: str, caption: str) -> str:
        post_id = f"mock_pub_{uuid.uuid4().hex[:10]}"
        self.published_items.append({
            'post_id': post_id,
            'asset_id': asset_id,
            'caption': caption,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'simulated': True,
        })
        return post_id
