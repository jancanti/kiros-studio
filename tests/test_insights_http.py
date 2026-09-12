import http.client
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from kiros.__main__ import make_server
from kiros.application import Application
from kiros.insights import TREND_FIELDS


class InsightsHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = make_server(self.tmp.name, 0)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.service = Application(Path(self.tmp.name)).insights

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, data=None, origin=True, raw=None, kind='application/x-www-form-urlencoded'):
        conn = http.client.HTTPConnection('127.0.0.1', self.port)
        headers = {'Content-Type': kind}
        if origin:
            headers['Origin'] = f'http://127.0.0.1:{self.port}'
        body = raw if raw is not None else (urlencode(data) if data is not None else None)
        conn.request('POST' if body is not None else 'GET', path, body, headers)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode()
        conn.close()
        return result

    def test_tabs_empty_states_and_error_escape(self):
        for tab, expected in (('diversity', 'Mapa de saturação'), ('sources', 'Fontes e tendências'),
                              ('experiments', 'Experimentos A/B')):
            status, headers, html = self.request('/insights?' + urlencode({'tab': tab, 'error': '<script>alert(1)</script>'}))
            self.assertEqual(status, 200)
            self.assertIn(expected, html)
            self.assertNotIn('<script>', html)
            self.assertIn('&lt;script&gt;', html)
            self.assertIn('Content-Security-Policy', headers)
        self.assertEqual(self.request('/insights?days=invalid')[0], 200)

    def test_origin_duplicate_fields_and_bad_payloads_blocked(self):
        path = '/api/insights/experiment'
        self.assertEqual(self.request(path, {'hypothesis': 'x'}, origin=False)[0], 403)
        self.assertEqual(self.request(path, raw='id=a&id=b')[0], 303)
        self.assertEqual(self.request(path, raw='{}', kind='application/json')[0], 415)
        self.assertIn('error=', self.request('/api/insights/unknown', {'x': 'y'})[1]['Location'])
        self.assertEqual(self.service.experiments(), [])

    def test_http_experiment_end_to_end_authority_and_small_sample(self):
        path = '/api/insights/'
        status, headers, _ = self.request(path + 'experiment', {'hypothesis': 'Mais cliques?', 'control': 'A',
            'variant': 'B', 'variable': 'copy', 'metric': 'Cliques por visita', 'authorization': 'Genérica', 'operator': 'Ana'})
        self.assertEqual(status, 303)
        self.assertIn('saved=1', headers['Location'])
        eid = self.service.experiments()[0]['id']
        self.assertIn('error=', self.request(path + 'start', {'id': eid, 'operator': 'Ana'})[1]['Location'])
        self.assertIn('error=', self.request(path + 'approve', {'id': eid, 'operator': 'Ana', 'authorization': 'Específica'})[1]['Location'])
        self.assertIn('saved=1', self.request(path + 'approve', {'id': eid, 'operator': 'Ana',
                      'authorization': 'Específica', 'confirmation': '1'})[1]['Location'])
        self.request(path + 'start', {'id': eid, 'operator': 'Ana'})
        self.request(path + 'result', {'id': eid, 'operator': 'Ana', 'source': 'CSV',
                      'control_sample': '4', 'control_successes': '0', 'variant_sample': '4', 'variant_successes': '4'})
        html = self.request('/insights?tab=experiments')[2]
        self.assertIn('Sem vencedor declarado', html)
        self.assertIn('amostra pequena', html)
        self.assertIn('CSV', html)
        self.assertEqual(self.service.experiments()[0]['state'], 'completed')

    def test_observation_persists_and_untrusted_text_stays_text(self):
        _, headers, _ = self.request('/api/insights/observation', {'title': '<script>test</script>',
            'dim_palette': 'Verde', 'occurred_at': '2026-01-01T10:00:00Z', 'source': 'Documento',
            'intentional_reason': 'Série editorial'})
        self.assertIn('saved=1', headers['Location'])
        html = self.request('/insights?days=365')[2]
        self.assertIn('&lt;script&gt;test&lt;/script&gt;', html)
        self.assertIn('Série editorial', html)

    def test_source_form_discovery_and_mock_labels(self):
        data = {key: 'Avaliação local ' + key for key in TREND_FIELDS}
        data.update(profile='Perfil simulado', category='Arquitetura', location='Sorocaba', source='Fixture local',
                    observed_at='2026-01-01T12:00:00Z', observation='<b>Texto externo</b>', is_mock='1')
        _, headers, _ = self.request('/api/insights/source', data)
        self.assertIn('saved=1', headers['Location'])
        self.assertNotIn('Perfil simulado', self.request('/insights?tab=sources')[2])
        html = self.request('/insights?tab=sources&category=arquitetura&location=sorocaba&include_mock=1')[2]
        self.assertIn('Simulação local — dados fictícios', html)
        self.assertIn('&lt;b&gt;Texto externo&lt;/b&gt;', html)
        self.assertIn('Interpretação KIROS', html)
        self.assertIn('Fonte: Fixture local', html)


if __name__ == '__main__':
    unittest.main()
