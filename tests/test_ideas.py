"""Testes unitários para Banco de Ideias, pilares, sazonalidade e conteúdo adjacente (M03-A03, M03-A04)."""
from datetime import date
from pathlib import Path
import tempfile
import unittest

from kiros.application import Application
from kiros.core.contracts import Provenance
from kiros.director.ideas import (
    INITIAL_PILLARS,
    MAX_ACTIVE_IDEAS_PER_PILLAR,
    IdeaBank,
)


class IdeaBankTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.ideas = self.app.idea_bank

    def provenance(self, ref='teste-ideias'):
        return Provenance('user', ref, '2026-09-12T12:00:00+00:00')

    def test_initial_six_pillars_and_propose_other(self):
        # M03-A03: Seis pilares iniciais
        pillars = self.ideas.list_pillars()
        pillar_ids = {p['id'] for p in pillars}
        self.assertEqual(pillar_ids, set(INITIAL_PILLARS))

        # Proposta de novo pilar ("Outro") não cria oficialmente sem aprovação (Seção 14)
        proposal = self.ideas.propose_new_pillar('Sustentabilidade', 'Foco em reciclagem de frascos de vidro')
        self.assertFalse(proposal['is_official'])
        self.assertTrue(proposal['requires_user_approval'])
        self.assertEqual(proposal['status'], 'proposal_pending_approval')
        # Pilares oficiais permanecem exatamente 6
        self.assertEqual(len(self.ideas.list_pillars()), 6)

    def test_active_ideas_limit_per_pillar(self):
        # M03-A03: Limite de cinco ideias ativas por pilar
        pillar = 'produtos'
        for i in range(MAX_ACTIVE_IDEAS_PER_PILLAR):
            self.ideas.add_idea(
                title=f"Ideia de Produto {i+1}",
                concept=f"Conceito exclusivo número {i+1} para linha de difusores",
                pillar=pillar,
                provenance=self.provenance(),
            )

        self.assertEqual(self.ideas.count_active_ideas(pillar), MAX_ACTIVE_IDEAS_PER_PILLAR)

        # Tentativa de adicionar a 6ª ideia ativa deve ser recusada
        with self.assertRaises(ValueError) as ctx:
            self.ideas.add_idea(
                title="Ideia Excedente",
                concept="Tentativa de ultrapassar o teto de cinco ideias ativas",
                pillar=pillar,
                provenance=self.provenance(),
            )
        self.assertIn("Limite de 5 ideias ativas atingido", str(ctx.exception))

    def test_pin_and_rejection_prevents_superficial_re_presentation(self):
        # M03-A03: Fixar/bloquear, rejeitar e arquivar com motivo impedem reapresentação superficial
        pillar = 'lifestyle'
        iid = self.ideas.add_idea(
            title="Sessão de Meditação Matinal com Bergamota",
            concept="Mostrar rotina de acordar e meditar usando o aroma cítrico",
            pillar=pillar,
            provenance=self.provenance(),
            is_pinned=True,
        )
        idea = self.ideas.list_ideas(pillar)[0]
        self.assertTrue(idea['is_pinned'])
        self.assertEqual(idea['state'], 'pinned')

        # Desafixa
        self.ideas.pin_idea(iid, is_pinned=False)
        self.assertFalse(self.ideas.list_ideas(pillar)[0]['is_pinned'])

        # Rejeitar sem motivo é recusado
        with self.assertRaises(ValueError):
            self.ideas.reject_idea(iid, reason="   ")

        # Rejeita com motivo
        self.ideas.reject_idea(iid, reason="Tom excessivamente esotérico para o posicionamento minimalista da KIROS")
        rejected_idea = self.ideas.list_ideas(pillar)[0]
        self.assertEqual(rejected_idea['state'], 'rejected')
        self.assertIn("esotérico", rejected_idea['rejection_reason'])

        # Como foi rejeitada (inativa), agora há espaço para uma nova ideia
        self.assertEqual(self.ideas.count_active_ideas(pillar), 0)

        # Porém, tentar reapresentar a mesma ideia com alteração superficial é bloqueado
        superficial = "Rotina de Meditação Matinal com Aroma Bergamota"
        with self.assertRaises(ValueError) as ctx:
            self.ideas.add_idea(
                title=superficial,
                concept="Acordar e meditar usando o aroma cítrico suave",
                pillar=pillar,
                provenance=self.provenance(),
            )
        self.assertIn("Reapresentação superficial impedida", str(ctx.exception))

    def test_adjacent_content_explains_audience_relation_and_bridge(self):
        # M03-A04: Conteúdo adjacente explica público, relação com KIROS e ponte
        suggestions = IdeaBank.generate_adjacent_content_suggestions("desaceleração no lar")
        self.assertGreater(len(suggestions), 0)
        for s in suggestions:
            self.assertIn('title', s)
            self.assertIn('why_attracts_audience', s)
            self.assertIn('relation_to_brand', s)
            self.assertIn('bridge_to_brand', s)
            self.assertEqual(s['funnel_stage'], 'Descoberta' if s['pillar'] == 'lifestyle' else 'Interesse')
            # Textos com substância concreta
            self.assertGreater(len(s['why_attracts_audience']), 15)
            self.assertGreater(len(s['relation_to_brand']), 15)
            self.assertGreater(len(s['bridge_to_brand']), 15)

    def test_seasonal_planning_priorities_and_phases_without_official_calendar(self):
        # M03-A04: Datas prioritárias geram rascunhos 2–3 meses antes, sem oficializar calendário
        # Simula data em 15 de outubro (aproximadamente 70 dias antes do Natal)
        ref_date = date(2026, 10, 15)
        opportunities = IdeaBank.get_seasonal_opportunities(reference_date=ref_date)

        natal_op = next((op for op in opportunities if op['event_name'] == 'Natal'), None)
        self.assertIsNotNone(natal_op)
        self.assertEqual(natal_op['days_until'], 71)
        self.assertTrue(natal_op['in_planning_window'])  # Dentro da janela de 2-3 meses (45-100 dias)
        self.assertEqual(natal_op['current_phase'], 'Warm-up')
        self.assertTrue(natal_op['is_draft'])
        self.assertFalse(natal_op['in_official_calendar'])  # Não entra no calendário oficial sem aprovação

        # 4 fases previstas da Seção 15
        phase_names = [p['phase'] for p in natal_op['phases']]
        self.assertEqual(phase_names, ['Warm-up', 'Consideração', 'Conversão', 'Last Call'])


if __name__ == '__main__':
    unittest.main()

