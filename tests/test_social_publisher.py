"""Testes do SocialPublisher e Auditoria Pré-Publicação no Instagram (M09-A03, M09-A04, M09-A05, M09-A06)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from kiros.infrastructure.local import SQLiteDatabase, FileStorage
from kiros.infrastructure.security import Policy, ExternalGateway, Secret
from kiros.core.contracts import Provenance
from kiros.social.models import (
    SocialPublication,
    AccountStatus,
    INSTAGRAM_PERMISSIONS,
    MAX_POSTS_PER_24_HOURS,
    MIN_SCHEDULE_AHEAD_SECONDS,
    MAX_SCHEDULE_AHEAD_SECONDS,
    SUPPORTED_ASPECT_RATIOS,
)
from kiros.social.audit import PublicationAuditor
from kiros.social.publisher import InstagramPublisher, MockSocialPublisher, InstagramAPIError
from kiros.campaigns.manager import CampaignManager
from kiros.cost import CostManager
from kiros.providers.manager import ProviderManager
from kiros.providers.router import ImageEngineRouter
from kiros.execution.queue import ExecutionQueue
from kiros.content import PrePublishAuditor, CopyEngine, StoriesEngine


class SocialPublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.db = SQLiteDatabase(self.data_dir / 'studio.sqlite3')
        self.storage = FileStorage(self.data_dir / 'files')
        self.policy = Policy(mode='mock', allow_publish=False)
        self.gateway = ExternalGateway(self.policy)
        self.cost = CostManager(self.db)
        self.providers = ProviderManager(self.db, self.gateway)
        self.router = ImageEngineRouter(self.db, self.providers)
        self.queue = ExecutionQueue(self.db, self.cost)
        self.copy_engine = CopyEngine()
        self.stories_engine = StoriesEngine()
        self.pre_auditor = PrePublishAuditor(self.copy_engine, self.stories_engine)
        self.campaigns = CampaignManager(
            self.db,
            self.cost,
            self.router,
            self.queue,
            pre_publish_auditor=self.pre_auditor,
        )
        self.auditor = PublicationAuditor(
            campaigns=self.campaigns,
            pre_publish_auditor=self.pre_auditor,
        )
        self.publisher = InstagramPublisher(
            database=self.db,
            gateway=self.gateway,
            auditor=self.auditor,
            mock_mode=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    # -------------------------------------------------------------------------
    # M09-A03: Fluxo Operacional Meta Graph API, Contas, Permissões e Formatos
    # -------------------------------------------------------------------------

    def test_account_permissions_and_publishing_limits_documented(self):
        """M09-A03: Contas, permissões oficiais e cotas ficam documentados e verificáveis."""
        status = self.publisher.get_account_status()
        self.assertIsNotNone(status.account_id)
        self.assertEqual(status.account_type, 'business')
        self.assertEqual(status.connection_status, 'mock')
        # Verifica as 4 permissões oficiais exigidas pela Meta
        for perm in ('instagram_basic', 'instagram_content_publish', 'pages_show_list', 'pages_read_engagement'):
            self.assertIn(perm, status.permissions)
        # Limite de 25 posts por 24h
        self.assertEqual(status.rate_limit_total, 25)
        self.assertEqual(status.rate_limit_remaining, 25)

    def test_supported_formats_and_aspect_ratios(self):
        """M09-A03: Formatos suportados (1:1, 4:5, 9:16) e limitações oficiais."""
        # 1:1 Quadrado
        self.assertIn('1:1', SUPPORTED_ASPECT_RATIOS)
        self.assertEqual(SUPPORTED_ASPECT_RATIOS['1:1']['ratio'], 1.0)
        # 4:5 Retrato feed
        self.assertIn('4:5', SUPPORTED_ASPECT_RATIOS)
        self.assertEqual(SUPPORTED_ASPECT_RATIOS['4:5']['ratio'], 0.8)
        # 9:16 Stories vertical
        self.assertIn('9:16', SUPPORTED_ASPECT_RATIOS)
        self.assertEqual(SUPPORTED_ASPECT_RATIOS['9:16']['ratio'], 0.5625)

        # Formato inválido deve ser reprovado pelo auditor
        audit_invalid_format = self.auditor.audit_for_publication(
            campaign_id=None,
            asset_id='asset_123',
            caption_text='Legenda limpa sem erros.',
            aspect_ratio='21:9',  # Proporção ultra-wide não suportada no feed/stories
            explicit_confirmation=True,
            confirmed_by='Operador KIROS',
        )
        self.assertFalse(audit_invalid_format.is_ready)
        self.assertTrue(any('Proporção' in r for r in audit_invalid_format.blocked_reasons))

    # -------------------------------------------------------------------------
    # M09-A04: Auditoria de Versão, Fidelidade, Copy, Direitos, Formatos e Comercial
    # -------------------------------------------------------------------------

    def test_audit_blocks_modified_version_after_approval(self):
        """M09-A04, M09-A05: Auditoria bloqueia campanha com versão modificada após aprovação."""
        camp_id = self.campaigns.create_campaign('Velas Botânicas', {'goal': 'vendas'}, {}, [])
        self.campaigns.add_storyboard_slide(camp_id, 'Slide 1', 'Vela acesa na mesa', 'close-up')
        self.campaigns.approve_campaign(camp_id, approver='Diretor Criativo')

        # Campanha aprovada
        camp = self.campaigns.get_campaign(camp_id)
        self.assertEqual(camp.plan_version, camp.approved_version)

        # Auditoria para publicação passa
        audit_ok = self.auditor.audit_for_publication(
            campaign_id=camp_id,
            asset_id='asset_vela',
            caption_text='Aroma que transforma sua casa. Conheça no link da bio.',
            explicit_confirmation=True,
            confirmed_by='Operador KIROS',
        )
        self.assertTrue(audit_ok.is_ready)

        # Agora modifica a campanha (adiciona outro slide), o que incrementa plan_version e invalida aprovação
        self.campaigns.add_storyboard_slide(camp_id, 'Slide 2', 'Detalhe da cera de coco', 'detail')
        camp_modified = self.campaigns.get_campaign(camp_id)
        self.assertEqual(camp_modified.status, 'draft')
        self.assertIsNone(camp_modified.approved_version)

        # Auditoria agora DEVE BLOQUEAR categoricamente
        audit_blocked = self.auditor.audit_for_publication(
            campaign_id=camp_id,
            asset_id='asset_vela',
            caption_text='Aroma que transforma sua casa. Conheça no link da bio.',
            explicit_confirmation=True,
            confirmed_by='Operador KIROS',
        )
        self.assertFalse(audit_blocked.is_ready)
        self.assertTrue(any('Versão modificada após aprovação' in r for r in audit_blocked.blocked_reasons))

    def test_audit_blocks_forbidden_emojis_and_ai_cliches(self):
        """M09-A04, Seções 34-36: Auditoria bloqueia emojis e clichês artificiais de IA."""
        audit_emoji = self.auditor.audit_for_publication(
            campaign_id=None,
            asset_id='asset_1',
            caption_text='Novo aroma incrível para você 🌿✨ aproveite!',
            explicit_confirmation=True,
            confirmed_by='Operador KIROS',
        )
        self.assertFalse(audit_emoji.is_ready)
        self.assertTrue(any('Emojis proibidos' in r for r in audit_emoji.blocked_reasons))

        audit_cliche = self.auditor.audit_for_publication(
            campaign_id=None,
            asset_id='asset_2',
            caption_text='Transforme seu ambiente e mergulhe em uma experiência com aconchego e sofisticação em cada detalhe.',
            explicit_confirmation=True,
            confirmed_by='Operador KIROS',
        )
        self.assertFalse(audit_cliche.is_ready)
        self.assertTrue(any('Clichês de IA' in r for r in audit_cliche.blocked_reasons))

    # -------------------------------------------------------------------------
    # M09-A05: Agendamento, Timezone, Recusa sem Confirmação, Falhas e Idempotência
    # -------------------------------------------------------------------------

    def test_publish_refusal_without_explicit_confirmation(self):
        """M09-A04, M09-A05, Seção 79: Recusa sem confirmação explícita de operador humano."""
        with self.assertRaises(PermissionError) as ctx:
            self.publisher.publish(
                asset_id='asset_123',
                caption='Aroma para casa feito em Sorocaba.',
                explicit_confirmation=False,  # Sem confirmação!
                confirmed_by='',
            )
        self.assertIn('Publicação exige confirmação explícita de operador humano (Seção 79)', str(ctx.exception))

    def test_scheduling_requires_timezone_aware_datetime(self):
        """M09-A05: Agendamento exige datetime com timezone explícito; rejeita naive datetime."""
        # 1. Naive datetime (sem timezone) é categoricamente rejeitado
        with self.assertRaises(ValueError) as ctx:
            self.publisher.publish(
                asset_id='asset_123',
                caption='Aroma floral suave.',
                scheduled_time_iso='2026-10-20T19:00:00',  # Sem timezone!
                explicit_confirmation=True,
                confirmed_by='Operador KIROS',
            )
        self.assertIn('deve incluir fuso horário explícito', str(ctx.exception))

        # 2. Timezone válido (UTC) mais de 15 minutos no futuro é aceito
        future_dt = datetime.now(timezone.utc) + timedelta(hours=2)
        post_id = self.publisher.publish(
            asset_id='asset_123',
            caption='Aroma floral suave para sua casa.',
            scheduled_time_iso=future_dt.isoformat(),
            explicit_confirmation=True,
            confirmed_by='Operador KIROS',
        )
        self.assertTrue(post_id.startswith('ig_scheduled_'))

    def test_scheduling_limits_enforced(self):
        """M09-A05: Limites oficiais da Meta: mínimo 15min e máximo 75 dias."""
        # Menos de 15 minutos no futuro (ex: 5 minutos)
        too_soon = datetime.now(timezone.utc) + timedelta(minutes=5)
        with self.assertRaises(ValueError) as ctx:
            self.publisher.publish(
                asset_id='asset_123',
                caption='Aroma floral suave para sua casa.',
                scheduled_time_iso=too_soon.isoformat(),
                explicit_confirmation=True,
                confirmed_by='Operador KIROS',
            )
        self.assertIn('no mínimo 15 minutos', str(ctx.exception))

        # Mais de 75 dias no futuro (ex: 80 dias)
        too_late = datetime.now(timezone.utc) + timedelta(days=80)
        with self.assertRaises(ValueError) as ctx:
            self.publisher.publish(
                asset_id='asset_123',
                caption='Aroma floral suave para sua casa.',
                scheduled_time_iso=too_late.isoformat(),
                explicit_confirmation=True,
                confirmed_by='Operador KIROS',
            )
        self.assertIn('não pode exceder o limite oficial da Meta de 75 dias', str(ctx.exception))

    def test_idempotency_prevents_duplicate_publishing(self):
        """M09-A05, Seção 68: Idempotência previne publicação duplicada ao reexecutar com mesma chave."""
        caption = 'Difusor de varetas com notas amadeiradas.'
        key = 'idempotency_fixed_test_key_12345'

        # Primeira chamada
        post_id_1 = self.publisher.publish(
            asset_id='asset_madeira',
            caption=caption,
            explicit_confirmation=True,
            confirmed_by='Operador KIROS',
            idempotency_key=key,
        )
        self.assertIsNotNone(post_id_1)

        # Segunda chamada com exatamente a mesma chave de idempotência
        post_id_2 = self.publisher.publish(
            asset_id='asset_madeira',
            caption=caption,
            explicit_confirmation=True,
            confirmed_by='Operador KIROS',
            idempotency_key=key,
        )
        # Deve retornar o mesmo post ID e não criar outro registro
        self.assertEqual(post_id_1, post_id_2)

        # Verifica no banco de dados que só existe exatamente 1 publicação com esta chave
        with self.publisher._connection() as conn:
            count = conn.execute(
                'SELECT COUNT(*) as c FROM social_publications WHERE idempotency_key = ?',
                (key,)
            ).fetchone()['c']
            self.assertEqual(count, 1)

    def test_service_unavailable_503_and_structured_error(self):
        """M09-A05, Seção 69: Simulação de indisponibilidade (503) com detalhes estruturados."""
        self.publisher.simulate_service_unavailable = True

        with self.assertRaises(InstagramAPIError) as ctx:
            self.publisher.publish(
                asset_id='asset_503',
                caption='Velas de lavanda feitas à mão.',
                explicit_confirmation=True,
                confirmed_by='Operador KIROS',
            )
        err = ctx.exception
        self.assertEqual(err.provider, 'meta_instagram_graph_api')
        self.assertEqual(err.stage, 'create_media_container')
        self.assertEqual(err.status_code, 503)
        self.assertIn('temporariamente indisponível', err.cause)
        self.assertIn('Aguardar estabilização', err.suggested_fix)

    def test_rate_limit_429_handling(self):
        """M09-A05, Seção 69: Simulação de cota esgotada (429) com diagnóstico estruturado."""
        self.publisher.simulate_rate_limit = True

        with self.assertRaises(InstagramAPIError) as ctx:
            self.publisher.publish(
                asset_id='asset_429',
                caption='Velas aromáticas de cera vegetal.',
                explicit_confirmation=True,
                confirmed_by='Operador KIROS',
            )
        err = ctx.exception
        self.assertEqual(err.provider, 'meta_instagram_graph_api')
        self.assertEqual(err.status_code, 429)
        self.assertIn('Limite de 25 publicações', err.cause)
        self.assertIn('Aguardar renovação', err.suggested_fix)

    # -------------------------------------------------------------------------
    # M09-A06: Governança de Modo Mock, Bloqueio de Rede e Não Exposição de Segredos
    # -------------------------------------------------------------------------

    def test_mock_mode_gateway_blocks_live_network(self):
        """M09-A06: Gateway bloqueia conexões de rede em modo mock."""
        # Se tentar executar operação de publicação ao vivo em modo mock pelo gateway
        with self.assertRaises(PermissionError) as ctx:
            self.gateway.call(lambda: 'live_network_response', paid=False, publish=True, approved=True)
        self.assertIn('Chamadas externas bloqueadas no modo mock', str(ctx.exception))

    def test_mock_mode_marks_simulated_and_never_leaks_secrets(self):
        """M09-A06, Seção 70: Provedor é marcado como mock e segredos nunca são expostos."""
        secret_token = Secret('EAAB_meta_secret_live_access_token_12345')
        self.assertEqual(str(secret_token), '[REDACTED]')

        # Status da conta é mock / unvalidated
        status = self.publisher.get_account_status()
        self.assertEqual(status.connection_status, 'mock')

        # Publicação via MockSocialPublisher
        mock_pub = MockSocialPublisher()
        res_id = mock_pub.publish('asset_100', 'Legenda de teste')
        self.assertEqual(len(mock_pub.published_items), 1)
        self.assertTrue(mock_pub.published_items[0]['simulated'])


if __name__ == '__main__':
    unittest.main()
