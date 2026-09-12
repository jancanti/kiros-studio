"""Testes unitários para o Creative Director, briefing híbrido e seleção de produtos (M03-A01, M03-A02, M03-A06)."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from kiros.application import Application
from kiros.core.contracts import Provenance


class CreativeDirectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.director = self.app.director
        self.library = self.app.library

        # Cadastra produtos de teste na biblioteca sem dados comerciais
        self.library.create_product('vela-alecrim', 'Vela Aromática Alecrim & Algodão', source='catalogo')
        self.library.create_product('difusor-bergamota', 'Difusor de Varetas Bergamota & Âmbar', source='catalogo')

    def provenance(self, ref='teste-diretor'):
        return Provenance('user', ref, '2026-09-12T12:00:00+00:00')

    def test_freeform_briefing_to_structured_conversion(self):
        # M03-A01: Briefing livre vira estrutura confirmável com perguntas mínimas agrupadas; objetivo, justificativa e confiança
        raw = "Quero lançar uma nova vela aromática em vidro âmbar para mostrar em ambientes sofisticados."
        prov = self.provenance('briefing-livre')
        structured = self.director.interpret_briefing(raw, provenance=prov)

        self.assertEqual(structured['primary_objective'], 'lançamento')
        self.assertIn('awareness', structured['secondary_objective'])
        self.assertGreater(structured['confidence'], 0.85)
        self.assertIn('novidade', structured['objective_justification'].lower())
        self.assertIn('visual_tone', structured)
        self.assertIn('Sofisticado', structured['visual_tone'])
        self.assertEqual(structured['status'], 'structured_draft')
        self.assertEqual(structured['provenance'], 'user')

        # Como mencionou vela, não deve fazer pergunta redundante sobre produto
        product_questions = [q for q in structured['grouped_questions'] if q['group'] == 'Produtos e Foco']
        self.assertEqual(len(product_questions), 0)

        # Pergunta de público agrupada de forma lógica e mínima
        audience_questions = [q for q in structured['grouped_questions'] if q['group'] == 'Público e Ocasião']
        self.assertEqual(len(audience_questions), 1)
        self.assertFalse(audience_questions[0]['required'])

    def test_objective_recommendation_matrix(self):
        # M03-A01 e Seção 12: suporte a vendas, lançamento, awareness, educação, relacionamento, sazonal
        tests = [
            ("Campanha promocional para acelerar vendas e faturamento de estoque", "vendas"),
            ("Guia educativo ensinando a aparar o pavio e cuidar da queima da vela", "educação"),
            ("Agradecer a comunidade e compartilhar a história familiar dos fundadores", "relacionamento"),
            ("Especial de Natal para kits de presentes exclusivos de fim de ano", "sazonal"),
            ("Apresentar a estética acolhedora e minimalista para novos seguidores", "awareness"),
        ]
        for prompt, expected_obj in tests:
            rec = self.director.recommend_objective(prompt)
            self.assertEqual(rec['primary_objective'], expected_obj, f"Falha para prompt: {prompt}")
            self.assertGreaterEqual(rec['confidence'], 0.70)
            self.assertTrue(len(rec['justification']) > 10)

    def test_product_selection_without_commercial_data(self):
        # M03-A06: Seleção de produto sem dados comerciais (sem vendas ou contagem comercial)
        # Os produtos cadastrados não possuem nenhuma importação de vendas nem estoque
        selected = self.director.select_products_for_concept("Vela Alecrim e acolhimento")
        self.assertGreater(len(selected), 0)
        self.assertEqual(selected[0]['product_id'], 'vela-alecrim')
        self.assertIn('Compatibilidade', selected[0]['selection_reason'])

        # Seleção geral de catálogo quando o tema é amplo
        selected_broad = self.director.select_products_for_concept("Ambiente de jantar de luxo")
        self.assertGreater(len(selected_broad), 0)

    def test_strategic_decisions_record_provenance(self):
        # M03-A02: Creative Director registra proveniência em decisões estratégicas
        prov = self.provenance('briefing-registro')
        self.director.interpret_briefing("Nova fragrância de flor de laranjeira para primavera", provenance=prov)

        # Consulta decisões no memory store
        with self.app.database.path as _:
            decisions = self.app.memory.query_memories(memory_types=['creative_decision'])
            # Decisão gravada em strategic_decisions
            import sqlite3
            with sqlite3.connect(self.app.database.path) as conn:
                row = conn.execute("SELECT * FROM strategic_decisions WHERE provenance='user'").fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[1], 'briefing_interpretation')
                self.assertIn('flor de laranjeira', row[3])


if __name__ == '__main__':
    unittest.main()

