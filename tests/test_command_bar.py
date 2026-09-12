"""Testes da Command Bar com Linguagem Natural e Governança (M11-A03 e M11-A05)."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from kiros.campaigns.manager import CampaignManager
from kiros.command_bar import CommandBarService
from kiros.cost import CostManager
from kiros.execution.queue import ExecutionQueue
from kiros.infrastructure.local import SQLiteDatabase
from kiros.providers.manager import ProviderManager
from kiros.providers.router import ImageEngineRouter
from kiros.search import GlobalSearchService


class CommandBarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        data_dir = Path(self.tmp.name)
        self.db = SQLiteDatabase(data_dir / 'studio.sqlite3')
        self.cost_manager = CostManager(self.db)
        self.router = ImageEngineRouter(self.db, ProviderManager(self.db, None))
        self.queue = ExecutionQueue(self.db, self.cost_manager)
        self.campaigns = CampaignManager(self.db, self.cost_manager, self.router, self.queue)
        self.search = GlobalSearchService(self.db)
        self.cmd_bar = CommandBarService(
            database=self.db,
            campaigns=self.campaigns,
            cost_manager=self.cost_manager,
            queue=self.queue,
            search_service=self.search,
        )

        # Popula uma campanha de teste via CampaignManager
        self.cid = self.campaigns.create_campaign(
            title='Lançamento Difusor Alecrim',
            briefing={'briefing_text': 'Difusor elegante', 'custom_objective': 'lançamento'},
            strategy={'tone': 'sofisticado'},
        )
        self.campaigns.add_storyboard_slide(
            campaign_id=self.cid,
            title='Slide Frasco',
            visual_prompt='Frasco de vidro',
        )
        self.campaigns.add_storyboard_slide(
            campaign_id=self.cid,
            title='Slide Ambiente',
            visual_prompt='Sala minimalista',
        )

    def test_open_last_campaign(self):
        """M11-A03: 'Abra a última campanha' navega para a campanha mais recente."""
        res = self.cmd_bar.execute('Abra a última campanha')
        self.assertEqual(res.action_type, 'navigate')
        self.assertTrue(res.executed)
        self.assertEqual(res.target_url, f'/conteudo?campaign_id={self.cid}')
        self.assertIn('Lançamento Difusor Alecrim', res.message)

    def test_show_ideas_of_pillar(self):
        """M11-A03: 'Mostre minhas ideias de Lifestyle' navega para o pilar correto."""
        res = self.cmd_bar.execute('Mostre minhas ideias de Lifestyle')
        self.assertEqual(res.action_type, 'navigate')
        self.assertTrue(res.executed)
        self.assertEqual(res.target_url, '/criar?pillar=lifestyle')
        self.assertIn('Lifestyle', res.message)

    def test_cost_query_calculates_without_spending_credits(self):
        """M11-A03: 'Quanto esta campanha vai custar?' calcula estimativa sem debitar créditos."""
        res = self.cmd_bar.execute('Quanto esta campanha vai custar?')
        self.assertEqual(res.action_type, 'info')
        self.assertTrue(res.executed)
        self.assertIsNotNone(res.impact)
        self.assertIn('estimated_cost', res.impact)
        self.assertIn('Nenhum crédito foi consumido', res.message)

    def test_compare_versions(self):
        """M11-A03: 'Compare as três últimas versões' direciona para a visualização comparativa."""
        res = self.cmd_bar.execute('Compare as três últimas versões')
        self.assertEqual(res.action_type, 'navigate')
        self.assertTrue(res.executed)
        self.assertIn('tab=compare', res.target_url)

    def test_reversible_actions_pause_and_resume(self):
        """M11-A03: Ações simples e reversíveis (pausar/retomar) executam diretamente."""
        # Pausa a geração
        res_pause = self.cmd_bar.execute('Pause a geração.')
        self.assertEqual(res_pause.action_type, 'reversible_action')
        self.assertTrue(res_pause.executed)
        self.assertTrue(res_pause.reversible)
        self.assertTrue(self.queue.is_paused())

        # Retoma a geração
        res_resume = self.cmd_bar.execute('Retome a geração.')
        self.assertEqual(res_resume.action_type, 'reversible_action')
        self.assertTrue(res_resume.executed)
        self.assertFalse(self.queue.is_paused())

    def test_actions_consuming_credits_disclose_impact_and_do_not_execute_automatically(self):
        """M11-A03: Ações que consomem créditos mostram impacto financeiro e exigem autorização."""
        res = self.cmd_bar.execute('Gerar imagens da campanha')
        self.assertEqual(res.action_type, 'credit_impact_required')
        self.assertFalse(res.executed)
        self.assertTrue(res.requires_confirmation)
        self.assertIsNotNone(res.impact)
        self.assertGreater(res.impact['estimated_cost'], 0.0)
        self.assertIn('consumirá créditos estimados', res.message)

    def test_publication_requires_explicit_confirmation_and_refuses_auto_publish(self):
        """M11-A03: Publicação exige confirmação e não executa automaticamente."""
        res = self.cmd_bar.execute('Publicar campanha no Instagram agora')
        self.assertEqual(res.action_type, 'publish_confirmation_required')
        self.assertFalse(res.executed)
        self.assertTrue(res.requires_confirmation)
        self.assertEqual(res.target_url, '/calendario')
        self.assertIn('auditoria prévia e confirmação explícita', res.message)

    def test_ambiguous_commands_explicitly_refused(self):
        """M11-A05: Recusa explícita de comando ambíguo para gastos ou publicação."""
        ambiguous_cases = ['publicar', 'postar', 'gastar', 'executar', 'gerar', 'lançar']
        for word in ambiguous_cases:
            res = self.cmd_bar.execute(word)
            self.assertEqual(res.action_type, 'ambiguous_refusal', f"Falhou para comando ambíguo: '{word}'")
            self.assertFalse(res.executed)
            self.assertIn('Comando ambíguo recusado', res.message)


if __name__ == '__main__':
    unittest.main()
