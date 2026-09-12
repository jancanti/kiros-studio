"""Testes do Serviço de Calendário Editorial e Recomendação Inteligente (M09-A01, M09-A02, Seções 39, 40, 41, 42)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from kiros.infrastructure.local import SQLiteDatabase, FileStorage
from kiros.core.contracts import Provenance
from kiros.calendar.models import (
    CalendarPreferences,
    CalendarEntry,
    TimeRecommendation,
    VALID_PILLARS,
)
from kiros.calendar.service import EditorialCalendarService
from kiros.campaigns.manager import CampaignManager
from kiros.cost import CostManager
from kiros.providers.manager import ProviderManager
from kiros.providers.router import ImageEngineRouter
from kiros.execution.queue import ExecutionQueue
from kiros.infrastructure.security import Policy, ExternalGateway


class CalendarServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.db = SQLiteDatabase(self.data_dir / 'studio.sqlite3')
        self.storage = FileStorage(self.data_dir / 'files')
        self.cost = CostManager(self.db)
        self.gateway = ExternalGateway(Policy(mode='mock'))
        self.providers = ProviderManager(self.db, self.gateway)
        self.router = ImageEngineRouter(self.db, self.providers)
        self.queue = ExecutionQueue(self.db, self.cost)
        self.campaigns = CampaignManager(self.db, self.cost, self.router, self.queue)
        self.calendar = EditorialCalendarService(self.db, campaigns=self.campaigns)

    def tearDown(self):
        self.tmp.cleanup()

    # -------------------------------------------------------------------------
    # M09-A01: Organização de Conteúdo, Pilares, Sazonalidade e Frequência
    # -------------------------------------------------------------------------

    def test_create_and_organize_calendar_entries_with_pillars_and_priorities(self):
        """M09-A01: Organiza conteúdo, pilares e prioridades no calendário."""
        entry = self.calendar.create_entry(
            title='Velas Aromáticas para Desacelerar',
            content_type='feed',
            pillar='lifestyle',
            priority='medium',
            scheduled_for='2026-10-15T19:00:00+00:00',
            notes='Enfoque em autocuidado e rituais noturnos.',
        )
        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.title, 'Velas Aromáticas para Desacelerar')
        self.assertEqual(entry.pillar, 'lifestyle')
        self.assertEqual(entry.content_type, 'feed')
        self.assertEqual(entry.status, 'draft')
        self.assertEqual(entry.scheduled_for, '2026-10-15T19:00:00+00:00')

        # Listagem ordenada
        entries = self.calendar.list_entries(pillar='lifestyle')
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].id, entry.id)

    def test_seasonal_priority_dates_kept_as_drafts_without_campaign_approval(self):
        """M09-A01, Seção 15: Datas prioritárias geram rascunhos antecipados, mas não entram no calendário oficial sem aprovação."""
        # Criação de entrada sazonal com prioridade crítica sem aprovação
        entry = self.calendar.create_entry(
            title='Campanha Dia das Mães — Warm-up',
            content_type='feed',
            pillar='lancamento',
            priority='critical',
            seasonal_tag='dia_das_maes',
            phase='warm_up',
            status='scheduled',  # Tentativa de oficializar diretamente
            scheduled_for='2026-05-01T18:00:00+00:00',
        )
        # O serviço deve forçar status 'draft' porque a campanha não foi aprovada formalmente
        self.assertEqual(entry.status, 'draft')

        # Tentativa de atualizar status para 'scheduled' em data sazonal sem campanha aprovada deve ser rejeitada
        with self.assertRaises(ValueError) as ctx:
            self.calendar.update_entry(entry.id, status='scheduled')
        self.assertIn('Datas prioritárias não podem entrar no calendário oficial sem aprovação', str(ctx.exception))

    def test_add_campaign_to_calendar_requires_full_approval(self):
        """M09-A01, Seção 41: Campanha deve estar totalmente aprovada para ser adicionada oficialmente."""
        # Cria campanha em rascunho
        camp_id = self.campaigns.create_campaign('Coleção Outono', {'goal': 'vendas'}, {}, [])
        self.campaigns.add_storyboard_slide(camp_id, 'Slide 1', 'Difusor de Canela', 'close-up')

        # Tentativa de adicionar campanha não aprovada deve falhar
        with self.assertRaises(ValueError) as ctx:
            self.calendar.add_campaign_to_calendar(camp_id)
        self.assertIn('não está totalmente aprovada', str(ctx.exception))

        # Aprova a campanha formalmente
        self.campaigns.approve_campaign(camp_id, approver='Diretor Criativo')

        # Agora adiciona ao calendário
        entries = self.calendar.add_campaign_to_calendar(camp_id)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].campaign_id, camp_id)
        self.assertEqual(entries[0].status, 'scheduled')
        self.assertIsNotNone(entries[0].recommended_time)
        self.assertEqual(entries[0].time_accepted, True)

    def test_frequency_limits_and_saturation_detection(self):
        """M09-A01, Seção 40: Detecta sobreposição de posts e saturação por pilar na mesma semana."""
        # Configura preferências: máx 2 posts por semana, saturação de 1 por pilar
        self.calendar.save_preferences(
            max_posts_per_week=2,
            min_hours_between_posts=24,
            saturation_threshold=1,
        )

        base_dt = datetime(2026, 10, 14, 19, 0, 0, tzinfo=timezone.utc)  # Quarta-feira
        # Entrada 1: Quarta-feira, pilar 'educativo'
        self.calendar.create_entry(
            title='Como Usar Difusores',
            pillar='educativo',
            scheduled_for=base_dt.isoformat(),
            status='scheduled',
        )

        # Entrada 2: Quinta-feira, mesmo pilar 'educativo' (menos de 24h e saturação do pilar)
        next_dt = base_dt + timedelta(hours=18)
        check = self.calendar.check_frequency_and_saturation(
            target_time_iso=next_dt.isoformat(),
            pillar='educativo',
        )

        self.assertTrue(check['is_saturated'])
        self.assertTrue(check['is_interval_violated'])
        self.assertFalse(check['is_frequency_exceeded'])  # Ainda é o segundo post

        # Creative Director fornece recomendação estruturada
        rec = check['recommendation']
        self.assertIsNotNone(rec)
        self.assertIn('Creative Director identificou potencial conflito', rec['explanation'])
        self.assertIn('Recomendamos redistribuir o conteúdo', rec['justification'])
        self.assertTrue(rec['requires_approval'])

        # Se adicionar um terceiro post na mesma semana, deve acusar excesso de frequência
        entry3_dt = base_dt + timedelta(days=2)
        self.calendar.create_entry(
            title='Post Extra',
            pillar='lifestyle',
            scheduled_for=entry3_dt.isoformat(),
            status='scheduled',
        )

        check_overflow = self.calendar.check_frequency_and_saturation(
            target_time_iso=(base_dt + timedelta(days=3)).isoformat(),
            pillar='institucional',
        )
        self.assertTrue(check_overflow['is_frequency_exceeded'])

    # -------------------------------------------------------------------------
    # M09-A02: Recomendação com Camadas (KIROS -> Setor -> Geral) e Manual Sempre Vence
    # -------------------------------------------------------------------------

    def test_recommend_publish_time_layers_and_confidence(self):
        """M09-A02, Seção 42: Recomendação em camadas com fonte, confiança e disclaimer anti-certeza."""
        # Sem vendas locais, deve usar Camada 2: Setor
        rec_sector = self.calendar.recommend_best_time(content_type='feed', pillar='institucional')
        self.assertEqual(rec_sector.data_basis['layer'], 'setor')
        self.assertEqual(rec_sector.data_basis['confidence'], 0.60)
        self.assertIn('Benchmark Setorial', rec_sector.data_basis['source'])
        self.assertIn('Estimativa estatística', rec_sector.data_basis['disclaimer'])

        # Injeta vendas locais para ativar Camada 1: KIROS
        with sqlite3_connect(self.db.path) as db:
            db.execute("INSERT INTO products (id, name, provenance) VALUES ('prod_1', 'Difusor', 'user')")
            db.execute("INSERT INTO sales_imports (digest, provenance) VALUES ('dig_1', 'user')")
            db.execute(
                '''INSERT INTO sales (import_digest, product_id, sold_on, quantity, revenue) 
                   VALUES ('dig_1', 'prod_1', '2026-09-10', 5, '250.0')'''
            )
            db.commit()

        rec_kiros = self.calendar.recommend_best_time(content_type='feed', pillar='lifestyle')
        self.assertEqual(rec_kiros.data_basis['layer'], 'kiros')
        self.assertEqual(rec_kiros.data_basis['confidence'], 0.85)
        self.assertIn('KIROS', rec_kiros.data_basis['source'])
        self.assertIn('Estimativa estatística', rec_kiros.data_basis['disclaimer'])

    def test_manual_selected_time_always_wins_and_records_all_five_fields(self):
        """M09-A02, Seção 41: Manual sempre vence e registra os 5 campos obrigatórios."""
        entry = self.calendar.create_entry(
            title='Lançamento Difusor Alecrim',
            pillar='lancamento',
            content_type='feed',
        )

        rec = self.calendar.recommend_for_entry(entry.id)
        recommended_iso = rec.recommended_time

        # 1. Caso 1: Usuário aceita a recomendação
        entry_accepted = self.calendar.record_time_decision(
            entry_id=entry.id,
            selected_time_iso=recommended_iso,
            accept_recommendation=True,
            recommended_time_iso=recommended_iso,
            data_basis=rec.data_basis,
        )
        self.assertEqual(entry_accepted.recommended_time, recommended_iso)
        self.assertEqual(entry_accepted.selected_time, recommended_iso)
        self.assertTrue(entry_accepted.time_accepted)
        self.assertIn('layer', entry_accepted.data_basis)
        self.assertIsInstance(entry_accepted.later_performance, dict)

        # 2. Caso 2: Manual vence (usuário escolhe horário próprio diferente)
        custom_manual_time = '2026-11-20T14:15:00+00:00'
        entry_manual = self.calendar.record_time_decision(
            entry_id=entry.id,
            selected_time_iso=custom_manual_time,
            accept_recommendation=False,
            recommended_time_iso=recommended_iso,
            data_basis=rec.data_basis,
        )
        self.assertEqual(entry_manual.recommended_time, recommended_iso)
        self.assertEqual(entry_manual.selected_time, custom_manual_time)
        self.assertEqual(entry_manual.scheduled_for, custom_manual_time)
        self.assertFalse(entry_manual.time_accepted)  # Manual venceu!
        self.assertIn('layer', entry_manual.data_basis)
        self.assertIsInstance(entry_manual.later_performance, dict)


def sqlite3_connect(path):
    import sqlite3
    return sqlite3.connect(path)


if __name__ == '__main__':
    unittest.main()
