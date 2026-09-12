from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from kiros.application import Application
from kiros.insights import InsightsService, DIMENSIONS, TREND_FIELDS


class InsightsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.service = InsightsService(self.app.database, lambda: datetime(2026, 9, 12, 18, tzinfo=timezone.utc))

    def experiment(self, variable='framing', **kwargs):
        return self.service.create_experiment('Plano aberto aumenta cliques?', 'Plano fechado',
                                              'Plano aberto', variable, 'Visitas com clique', **kwargs)

    def test_saturation_all_dimensions_and_intentional_repeat_survive_restart(self):
        dims = {key: 'Valor observado' for key in DIMENSIONS}
        for i in range(3):
            self.service.record_diversity(f'Post {i}', dims, '2026-09-12T12:00:00-03:00',
                                          'Arquivo editorial', intentional_reason='Série intencional de lançamento')
        reopened = InsightsService(self.app.database, self.service.clock)
        report = reopened.saturation(7)
        self.assertEqual(len(report['map']), len(DIMENSIONS))
        self.assertEqual(report['missing_dimensions'], [])
        self.assertTrue(all(row['warning'] and row['count'] == 3 for row in report['map']))
        self.assertTrue(all(row['per_week'] == 3 for row in report['map']))
        self.assertEqual(report['samples'][0]['intentional_reason'], 'Série intencional de lançamento')
        self.assertEqual(report['map'][0]['last_seen'], '2026-09-12T15:00:00+00:00')

    def test_missing_values_recency_and_calendar_scope_are_not_invented(self):
        self.service.record_diversity('Antigo', {'palette': 'verde'}, '2026-01-01T00:00:00+00:00', 'arquivo')
        self.service.record_diversity('Atual', {'palette': 'verde'}, '2026-09-12T12:00:00+00:00', 'arquivo')
        self.service.record_diversity('Sem paleta', {'format': 'feed'}, '2026-09-12T12:00:00+00:00', 'arquivo')
        with self.service.connect() as conn:
            conn.execute("INSERT INTO calendar_entries (id,title,pillar,status,scheduled_for,created_at,updated_at) "
                         "VALUES ('cal','Agendado','lifestyle','scheduled','2026-09-12T12:00:00Z','x','x')")
        report = self.service.saturation(7)
        palette = next(r for r in report['map'] if r['dimension'] == 'palette')
        self.assertEqual(palette['count'], 1)
        self.assertEqual(palette['unknown'], 1)
        self.assertFalse(palette['warning'])
        self.assertIn('Fragrância', report['missing_dimensions'])
        self.assertEqual(len(report['samples']), 3)
        self.assertEqual({r['scope'] for r in report['map']}, {'calendário', 'observação informada'})

    def test_observation_invalid_date_dimensions_and_campaign_rejected(self):
        for dims, when, campaign in [({}, '2026-09-12T12:00:00Z', None),
                                    ({'secret': 'x'}, '2026-09-12T12:00:00Z', None),
                                    ({'palette': 'x'}, '2026-09-12T12:00:00', None),
                                    ({'palette': 'x'}, '2030-09-12T12:00:00Z', None),
                                    ({'palette': 'x'}, '2026-09-12T12:00:00Z', 'missing')]:
            with self.subTest(dims=dims, when=when, campaign=campaign), self.assertRaises(ValueError):
                self.service.record_diversity('Teste', dims, when, 'fonte', campaign)
        self.assertEqual(self.service.saturation()['samples'], [])

    def test_competitive_discovery_preserves_provenance_all_trend_fields_and_mock_separation(self):
        trend = {key: 'Avaliação do operador: ' + key for key in TREND_FIELDS}
        for mock in (True, False):
            self.service.record_competitor('Referência informada', 'Decoração', 'Sorocaba',
                'Documento local página 2', '2026-09-10T10:00:00-03:00', 'Materiais naturais', trend, mock)
        self.assertEqual(len(self.service.discover(category='decoração', location='SOROCABA')), 1)
        self.assertEqual(len(self.service.discover(include_mock=True)), 2)
        self.assertEqual(self.service.discover(profile='inexistente'), [])
        self.assertEqual(self.service.discover(category='%'), [])
        item = self.service.discover()[0]
        self.assertEqual(item['trend'], trend)
        self.assertEqual(item['source'], 'Documento local página 2')
        self.assertEqual(item['observed_at'], '2026-09-10T13:00:00+00:00')
        self.assertEqual(item['recorded_at'], '2026-09-12T18:00:00+00:00')
        with self.assertRaises(ValueError):
            self.service.record_competitor('Perfil', 'Cat', 'SP', 'fonte', '2026-09-10', 'texto', trend)
        with self.assertRaises(ValueError):
            self.service.record_competitor('Perfil', 'Cat', 'SP', 'fonte', '2026-09-10T00:00:00Z', 'texto', {})

    def test_medium_high_cannot_inherit_low_risk_authority(self):
        for variable, expected in (('copy', 'medium'), ('product', 'high')):
            eid = self.experiment(variable, authorization='Autorização geral para enquadramento', operator='Ana')
            item = next(e for e in self.service.experiments() if e['id'] == eid)
            self.assertEqual(item['risk'], expected)
            self.assertEqual(item['state'], 'awaiting_approval')
            with self.assertRaises(PermissionError):
                self.service.start_experiment(eid, 'Ana')
            with self.assertRaises(PermissionError):
                self.service.approve_experiment(eid, 'Ana', 'true', 'Esta variante')
            self.service.approve_experiment(eid, 'Ana', True, 'Aprovo esta variante específica')
            self.service.start_experiment(eid, 'Ana')

    def test_low_risk_requires_authority_and_protected_change_escalates(self):
        eid = self.experiment()
        with self.assertRaises(PermissionError):
            self.service.start_experiment(eid, 'Ana')
        authorized = self.experiment(authorization='Brief aprovado: testar enquadramentos', operator='Ana')
        self.service.start_experiment(authorized, 'Ana')
        with self.assertRaises(PermissionError):
            self.service.start_experiment(authorized, 'Ana')
        protected = self.experiment(protected_change=True, authorization='Brief', operator='Ana')
        item = next(e for e in self.service.experiments() if e['id'] == protected)
        self.assertEqual(item['risk'], 'high')
        self.assertEqual(item['state'], 'awaiting_approval')

    def test_small_ab_sample_never_announces_winner_and_history_is_immutable(self):
        eid = self.experiment(authorization='Teste local autorizado', operator='Ana')
        with self.assertRaises(PermissionError):
            self.service.record_result(eid, 5, 0, 5, 5, 'CSV', 'Ana')
        self.service.start_experiment(eid, 'Ana')
        result = self.service.record_result(eid, 5, 0, 5, 5, 'CSV setembro', 'Ana')
        self.assertEqual(result['variant_rate'], 100)
        self.assertIn('amostra pequena', result['confidence'])
        self.assertIn('Sem vencedor', result['conclusion'])
        with self.assertRaises(PermissionError):
            self.service.record_result(eid, 1000, 0, 1000, 1000, 'Outra fonte', 'Ana')
        stored = InsightsService(self.app.database).experiments()[0]
        self.assertEqual(stored['result'], result)
        self.assertEqual(len(stored['events']), 3)
        self.assertEqual(stored['state'], 'completed')

    def test_invalid_samples_rejected_and_large_samples_still_descriptive(self):
        eid = self.experiment(authorization='Teste', operator='Ana')
        self.service.start_experiment(eid, 'Ana')
        for samples in ((0, 0, 1, 1), (1, 2, 1, 1), (-1, 0, 1, 0), (True, 1, 1, 1), (2.5, 1, 1, 1)):
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                self.service.record_result(eid, *samples, 'CSV', 'Ana')
        result = self.service.record_result(eid, 1000, 500, 1000, 700, 'CSV', 'Ana')
        self.assertEqual(result['control_rate'], 50)
        self.assertIn('descritiva', result['confidence'])
        self.assertIn('Sem vencedor', result['conclusion'])

    def test_experiment_constraints_and_failed_approval_are_atomic(self):
        with self.assertRaises(ValueError):
            self.experiment('invalid')
        with self.assertRaises(ValueError):
            self.experiment(authorization='Brief', operator='')
        eid = self.experiment('copy')
        with self.assertRaises(ValueError):
            self.service.approve_experiment(eid, '', True, 'Escopo')
        self.assertEqual(self.service.experiments()[0]['state'], 'awaiting_approval')
        self.assertEqual(len(self.service.experiments()[0]['events']), 1)
        self.service.approve_experiment(eid, 'Ana', True, 'Escopo')
        with self.assertRaises(ValueError):
            self.service.approve_experiment(eid, 'Outro', True, 'Escopo diferente')
        self.assertEqual(self.service.experiments()[0]['approved_by'], 'Ana')

    def test_no_external_calls_or_publications_for_any_experiment(self):
        from unittest.mock import patch
        with patch.object(self.app.gateway, 'call', side_effect=AssertionError('External call')):
            eid = self.experiment(authorization='Acompanhamento local', operator='Ana')
            self.service.start_experiment(eid, 'Ana')
            self.service.record_result(eid, 10, 2, 10, 4, 'CSV local', 'Ana')
        with self.service.connect() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM social_publications').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
