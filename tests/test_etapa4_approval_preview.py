"""Testes otimizados para a Etapa 4: Criar & Aprovar (Prévia, Edição In-Line e Regerar Slide)."""
import unittest
import tempfile
from pathlib import Path
from kiros.application import Application
from kiros.ui.campaigns import dispatch_campaign_action, render_approval_screen


class TestEtapa4ApprovalPreview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Application(Path(self.tmp.name))

        # Cria uma campanha base com 1 slide para os testes
        dispatch_campaign_action(
            self.app,
            'create',
            {
                'title': 'Campanha Teste Etapa 4',
                'briefing_text': 'Vela de alecrim em ambiente aconchegante',
                'custom_objective': 'awareness',
            }
        )
        self.cid = self.app.campaigns.list_campaigns()[0]['id']
        self.slide = self.app.campaigns.get_approval_screen_data(self.cid)['storyboard'][0]

    def tearDown(self):
        self.tmp.cleanup()

    def test_etapa4_update_text_inline(self):
        """Garante a edição de texto in-line direta na prévia do slide."""
        res_query = dispatch_campaign_action(
            self.app,
            'update_text_inline',
            {
                'campaign_id': self.cid,
                'slide_id': self.slide['id'],
                'title': 'Título Editado In-Line',
                'caption_draft': 'Legenda editada na prévia sem recriar a campanha.',
            }
        )

        self.assertIn(f'campaign_id={self.cid}', res_query)

        # Verifica que o título e legenda foram atualizados no banco de dados
        updated_slide = self.app.campaigns.get_approval_screen_data(self.cid)['storyboard'][0]
        self.assertEqual(updated_slide['title'], 'Título Editado In-Line')
        self.assertEqual(updated_slide['caption_draft'], 'Legenda editada na prévia sem recriar a campanha.')

    def test_etapa4_approve_and_schedule_auto(self):
        """Garante o agendamento automático em 1-clique no melhor horário do Instagram."""
        res_query = dispatch_campaign_action(
            self.app,
            'approve_and_schedule_auto',
            {
                'campaign_id': self.cid,
                'approver': 'Diretor de Criação',
            }
        )

        self.assertIn('agendada+automaticamente', res_query)

        # Verifica se a campanha ficou aprovada/enfileirada e se foi criada uma entrada no calendário
        camp = self.app.campaigns.get_campaign(self.cid)
        self.assertIn(camp.status, ('approved', 'queued'))

        entries = self.app.calendar.list_entries()
        self.assertGreaterEqual(len(entries), 1)
        self.assertEqual(entries[0].campaign_id, self.cid)

    def test_etapa4_approve_and_schedule_manual(self):
        """Garante o agendamento com data e hora manual."""
        res_query = dispatch_campaign_action(
            self.app,
            'approve_and_schedule_manual',
            {
                'campaign_id': self.cid,
                'approver': 'Diretor de Criação',
                'scheduled_date': '2026-10-15 19:30:00',
            }
        )

        self.assertIn('2026-10-15', res_query)

        entries = self.app.calendar.list_entries()
        self.assertGreaterEqual(len(entries), 1)

    def test_etapa4_render_approval_ui(self):
        """Garante a renderização dos botões duplos de agendamento e formulário in-line."""
        camp = self.app.campaigns.get_campaign(self.cid)
        html = render_approval_screen(self.app, camp, {})

        self.assertIn("⚡ Aprovar &amp; Agendar Automático (Melhor Horário @usekiros)", html)
        self.assertIn("📅 Agendar Data/Hora", html)
        self.assertIn("✏️ Edição Direta de Texto do Slide (In-Line)", html)
        self.assertIn("🎨 Intervenção Localizada · Regenerar Somente Este Slide", html)


if __name__ == '__main__':
    unittest.main()
