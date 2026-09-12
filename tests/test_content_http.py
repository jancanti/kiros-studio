"""Testes de Integração HTTP para Copy, Legendas, Stories e Auditoria Pré-Publicação (M08)."""
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request

from kiros.__main__ import make_server
from kiros.core.contracts import Provenance


class ContentHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)

        # Encontra porta livre
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            self.port = s.getsockname()[1]

        self.server = make_server(self.data_dir, port=self.port)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        time.sleep(0.1)

        self.app = self.server.app if hasattr(self.server, 'app') else None
        # Recupera Application do make_server closure se possível, ou instancia
        from kiros.application import Application
        self.app = Application(self.data_dir)

        # Cria campanha de teste com produto contendo preço real no briefing/produtos
        self.cid = self.app.campaigns.create_campaign(
            title="Campanha de Outono 2026",
            briefing={'visual_tone': 'Luz natural suave', 'summary': 'Velas aromáticas acolhedoras'},
            strategy={'funnel_stage': 'Descoberta'},
            products=[{
                'product_id': 'vela-alecrim-amber',
                'name': 'Vela Alecrim & Algodão',
                'price': '118,00',
            }],
            provenance=Provenance('user', 'test.content.http', '2026-09-12T12:00:00+00:00'),
        )
        self.s1_id = self.app.campaigns.add_storyboard_slide(
            campaign_id=self.cid,
            title="Slide 1: Manhã com Café",
            visual_prompt="Vela acesa sobre mesa de carvalho",
            caption_draft="Aroma suave para começar o dia.",
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp_dir.cleanup()

    def _post(self, path: str, data: dict, follow_redirects: bool = False):
        encoded = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=encoded,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Host': f'127.0.0.1:{self.port}',
                'Origin': f'http://127.0.0.1:{self.port}',
            },
            method='POST',
        )
        if not follow_redirects:
            class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None
            opener = urllib.request.build_opener(NoRedirectHandler)
            try:
                return opener.open(req)
            except urllib.error.HTTPError as err:
                return err
        return urllib.request.urlopen(req)

    def _get(self, path: str):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            headers={'Host': f'127.0.0.1:{self.port}'},
        )
        return urllib.request.urlopen(req)

    def test_slide_copy_update_and_ui_rendering_over_http(self):
        """M08-A01 e M08-A05: Comprova atualização de copy e renderização dos painéis via HTTP."""
        resp = self._post('/api/campaigns/update_slide_copy', {
            'campaign_id': self.cid,
            'slide_id': self.s1_id,
            'mode': 'automatic',
            'cta_mode': 'intent_based',
            'cta_intent': 'descoberta',
        })
        self.assertEqual(resp.status, 303)
        loc = resp.headers.get('Location', '')
        self.assertIn('msg=', loc)

        # GET /conteudo?campaign_id=... renderiza o painel de copy e checklist de auditoria
        get_resp = self._get(f'/conteudo?campaign_id={self.cid}')
        self.assertEqual(get_resp.status, 200)
        body = get_resp.read().decode('utf-8')
        self.assertIn('Legenda &amp; Governança Editorial', body)
        self.assertIn('Auditoria Pré-Publicação', body)
        self.assertIn('Planejador de Stories', body)

    def test_caption_suggestions_generation_over_http(self):
        """M08-A01: Comprova geração de 3 sugestões temáticas de legenda via HTTP."""
        resp = self._post('/api/campaigns/suggest_captions', {
            'campaign_id': self.cid,
            'slide_id': self.s1_id,
        })
        self.assertEqual(resp.status, 303)

        copy_obj = self.app.campaigns.get_slide_copy(self.s1_id)
        self.assertEqual(len(copy_obj.suggestions), 3)
        self.assertEqual({s['style'] for s in copy_obj.suggestions}, {'sensorial', 'rotina', 'minimalista'})

    def test_price_governance_rejection_and_approval_over_http(self):
        """M08-A02 e M08-A03: Preço só com justificativa e aprovação explícita via HTTP."""
        # 1. Tentativa de exibir preço sem justificativa -> Redireciona com erro
        resp_bad = self._post('/api/campaigns/update_slide_copy', {
            'campaign_id': self.cid,
            'slide_id': self.s1_id,
            'mode': 'automatic',
            'show_price': '1',
            'price_justification': '',
            'price_approved_by': '',
        })
        self.assertEqual(resp_bad.status, 303)
        self.assertIn('error=', resp_bad.headers.get('Location', ''))

        # 2. Exibição de preço com justificativa e aprovador -> Sucesso
        resp_ok = self._post('/api/campaigns/approve_price_display', {
            'campaign_id': self.cid,
            'slide_id': self.s1_id,
            'price_justification': 'Transparência em lançamento oficial',
            'price_approved_by': 'Diretoria Comercial',
        })
        self.assertEqual(resp_ok.status, 303)
        copy_obj = self.app.campaigns.get_slide_copy(self.s1_id)
        self.assertTrue(copy_obj.show_price)
        self.assertEqual(copy_obj.price_value, "R$ 118,00")
        self.assertEqual(copy_obj.price_approved_by, "Diretoria Comercial")

    def test_story_sequence_planning_over_http(self):
        """M08-A04: Criação e planejamento de sequência de Stories própria via HTTP."""
        resp = self._post('/api/campaigns/create_story_sequence', {
            'campaign_id': self.cid,
            'title': 'Sequência Outono 2026',
            'story_type': 'derived_from_campaign',
            'objective': 'Engajamento e rotinas matinais',
        })
        self.assertEqual(resp.status, 303)

        sequences = self.app.campaigns.list_story_sequences(campaign_id=self.cid)
        self.assertEqual(len(sequences), 1)
        seq = sequences[0]
        self.assertEqual(seq.title, 'Sequência Outono 2026')
        self.assertGreaterEqual(len(seq.frames), 3)

    def test_pre_publish_audit_endpoint_over_http(self):
        """M08-A05: Endpoint /api/content/audit retorna checklist estruturado em JSON."""
        # Audita o slide criado
        resp = self._get(f'/api/content/audit?slide_id={self.s1_id}')
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.read().decode('utf-8'))
        self.assertIn('is_ready', data)
        self.assertIn('checks', data)
        self.assertTrue(any(c['check_id'] == 'no_emojis' for c in data['checks']))
        self.assertTrue(any(c['check_id'] == 'no_auto_hashtags' for c in data['checks']))


if __name__ == '__main__':
    unittest.main()

