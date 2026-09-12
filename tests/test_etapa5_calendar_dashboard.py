"""Testes otimizados para a Etapa 5: Calendário & Fila Instagram (@usekiros) + Dashboard Redesenhado."""
import unittest
import tempfile
from pathlib import Path
from kiros.application import Application
from kiros.ui.calendar import dispatch_calendar_action, render_calendar
from kiros.ui.dashboard import render_dashboard


class TestEtapa5CalendarDashboard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Application(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_etapa5_calendar_ui_usekiros(self):
        """Garante que a UI do Calendário exibe a conta @usekiros e permite agendamentos."""
        entry = self.app.calendar.create_entry(
            title="Post Carrossel Velas de Outono",
            content_type="feed",
            pillar="institucional",
            scheduled_for="2026-10-20T18:00:00+00:00",
            status="scheduled",
        )
        self.assertIsNotNone(entry.id)

        html = render_calendar(self.app, {})
        self.assertIn("@usekiros", html)
        self.assertIn("Calendário Editorial", html)
        self.assertIn("Post Carrossel Velas de Outono", html)

    def test_etapa5_dashboard_ui_rendering(self):
        """Garante a renderização do Dashboard Contextual integrado."""
        html = render_dashboard(self.app, {})
        self.assertIn("@usekiros", html)
        self.assertIn("Visão Geral do Estúdio", html)
        self.assertIn("Hub de Ideias", html)
        self.assertIn("Criar Nova Campanha", html)

    def test_etapa5_publish_or_schedule_action(self):
        """Garante a publicação/agendamento com confirmação humana explícita."""
        entry = self.app.calendar.create_entry(
            title="Lançamento Vela Alecrim & Bergamota",
            content_type="feed",
            pillar="institucional",
            scheduled_for="2026-10-22T19:00:00+00:00",
            status="scheduled",
        )

        res = dispatch_calendar_action(
            self.app,
            'publish_or_schedule',
            {
                'entry_id': entry.id,
                'explicit_confirmation': '1',
                'confirmed_by': 'Diretor de Mídia',
                'caption': 'Legenda de teste para @usekiros',
            }
        )

        self.assertIn('processado+com+sucesso', res)


if __name__ == '__main__':
    unittest.main()
