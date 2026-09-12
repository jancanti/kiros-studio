"""Testes de Busca Global, Acentuação, Filtros e Preservação do Texto Original (M11-A02 e M11-A05)."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from kiros.core.contracts import Provenance
from kiros.director.ideas import IdeaBank
from kiros.director.memory import MemoryStore
from kiros.infrastructure.local import SQLiteDatabase, FileStorage
from kiros.layout import TemplateLibrary
from kiros.library import Library
from kiros.providers.mock import MockVision
from kiros.search import GlobalSearchService, normalize_text


class GlobalSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        data_dir = Path(self.tmp.name)
        self.db = SQLiteDatabase(data_dir / 'studio.sqlite3')
        self.storage = FileStorage(data_dir / 'files')
        self.library = Library(self.db, self.storage, MockVision())
        self.memory = MemoryStore(self.db)
        self.ideas = IdeaBank(self.db)
        self.templates = TemplateLibrary(self.db)
        self.search = GlobalSearchService(self.db)

        self._populate_sample_data()

    def _populate_sample_data(self):
        # 1. Produto com acento
        self.library.create_product('vela-lavanda', 'Vela Aromática de Lavanda & Cedro', 15, 'Manual')

        # 2. Imagem / Referência visual
        fixture_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4'
        self.library.add_reference(
            fixture_png,
            product_id='vela-lavanda',
            source_reference='Estúdio Fotográfico Sorocaba',
            rights='confirmed',
            angle='front',
        )

        with sqlite3.connect(self.db.path) as conn:
            # 3. Campanha com acento
            conn.execute(
                '''INSERT INTO campaigns (id, title, briefing_json, strategy_json, products_json, created_at, updated_at, provenance)
                   VALUES ('camp-sensorial', 'Lançamento Sensorial de Inverno', ?, '{}', '[]', '2026-09-12T10:00:00Z', '2026-09-12T10:00:00Z', 'user')''',
                (json.dumps({'briefing_text': 'Campanha de aconchego com essência amadeirada', 'custom_objective': 'lançamento'}),),
            )

            # 4. Versão
            conn.execute(
                '''INSERT INTO execution_versions (id, campaign_id, slide_id, step_id, version_number, provider_id, model_id, prompt, reason, fidelity_score, created_at)
                   VALUES ('vers-001', 'camp-sensorial', 'slide-1', 'step-1', 1, 'recraft_v3', 'recraft-20B', 'Frasco de vela âmbar em mesa rústica de carvalho', 'Exploração de textura', 89.2, '2026-09-12T10:30:00Z')'''
            )

            # 5. Ideia no banco de ideias
            conn.execute(
                '''INSERT INTO ideas (id, title, concept, pillar, state, is_pinned, rejection_reason, fingerprint, created_at, updated_at, provenance)
                   VALUES ('idea-001', 'Ritual Noturno com Difusor', 'Fotografia com iluminação quente de abajur criando atmosfera relaxante', 'lifestyle', 'approved', 1, NULL, 'fp-idea-001', '2026-09-12T09:00:00+00:00', '2026-09-12T09:00:00+00:00', 'user')'''
            )

            # 6. Template
            conn.execute(
                '''INSERT INTO layout_templates (id, name, family, status, supported_formats_json, composition_rules_json, default_elements_json, usage_count, last_used_at, created_at, updated_at, provenance)
                   VALUES ('tmpl-elegance', 'Minimalismo Editorial Nobre', 'editorial_minimalist', 'active', '["4:5"]', '{"description": "Layout assimétrico com tipografia Rubik e grande respiro"}', '[]', 0, NULL, '2026-09-12T08:00:00+00:00', '2026-09-12T08:00:00+00:00', 'user')'''
            )

            # 7. Decisão estratégica
            conn.execute(
                '''INSERT INTO strategic_decisions (id, decision_type, summary, details_json, created_at, provenance)
                   VALUES ('dec-001', 'palette_definition', 'Adoção da paleta verde floresta e terracota para outono', '{}', '2026-09-12T08:30:00Z', 'creative_director')'''
            )

            # 8. Histórico (cost_records e auditoria)
            conn.execute(
                '''INSERT INTO cost_records (campaign_id, asset_id, stage, provider, model, estimated_cost, actual_cost, generation_count, timestamp, provenance)
                   VALUES ('camp-sensorial', 'asset-1', 'generation', 'gemini', 'gemini-2.5-pro', 0.1250, 0.1250, 1, '2026-09-12T11:00:00+00:00', 'user')'''
            )

    def test_search_all_eight_entity_types(self):
        """M11-A02: Busca cobre os 8 alvos: campanhas, produtos, imagens, versões, ideias, templates, decisões e histórico."""
        # 1. Busca por campanha
        res_camp = self.search.search('Sensorial')
        self.assertTrue(any(r.entity_type == 'campaign' for r in res_camp))

        # 2. Busca por produto
        res_prod = self.search.search('Lavanda')
        self.assertTrue(any(r.entity_type == 'product' for r in res_prod))

        # 3. Busca por imagem/referência
        res_img = self.search.search('Fotográfico')
        self.assertTrue(any(r.entity_type == 'image' for r in res_img))

        # 4. Busca por versão
        res_vers = self.search.search('rústica carvalho')
        self.assertTrue(any(r.entity_type == 'version' for r in res_vers))

        # 5. Busca por ideia
        res_idea = self.search.search('Ritual Noturno')
        self.assertTrue(any(r.entity_type == 'idea' for r in res_idea))

        # 6. Busca por template
        res_tmpl = self.search.search('Minimalismo Editorial')
        self.assertTrue(any(r.entity_type == 'template' for r in res_tmpl))

        # 7. Busca por decisão
        res_dec = self.search.search('paleta verde floresta')
        self.assertTrue(any(r.entity_type == 'decision' for r in res_dec))

        # 8. Busca por histórico
        res_hist = self.search.search('gemini')
        self.assertTrue(any(r.entity_type == 'history' for r in res_hist))

    def test_case_and_accent_insensitivity_while_preserving_original_text(self):
        """M11-A02 e M11-A05: Ignora acentos e caixa alta/baixa preservando o texto original intacto."""
        # Busca com acento casa texto sem acento, e vice-versa:
        # Produto cadastrado: 'Vela Aromática de Lavanda & Cedro'
        # Busca: 'aromatica' (sem acento e minúscula)
        results = self.search.search('aromatica lavanda')
        self.assertGreaterEqual(len(results), 1)
        found = [r for r in results if r.entity_type == 'product'][0]

        # Comprova preservação exata do texto original cadastrado (com acentos e maiúsculas)
        self.assertEqual(found.title, 'Vela Aromática de Lavanda & Cedro')
        self.assertIn('vela-lavanda', found.snippet)

        # Campanha cadastrada: 'Lançamento Sensorial de Inverno'
        # Busca sem acento: 'lancamento'
        camp_results = self.search.search('lancamento sensorial')
        self.assertGreaterEqual(len(camp_results), 1)
        camp_found = [r for r in camp_results if r.entity_type == 'campaign'][0]
        self.assertEqual(camp_found.title, 'Lançamento Sensorial de Inverno')

        # Busca com acento invertido ou mistura de maiúsculas:
        mixed_results = self.search.search('LANÇAMENTO INVERNO')
        self.assertTrue(any(r.title == 'Lançamento Sensorial de Inverno' for r in mixed_results))

    def test_filtering_by_entity_type(self):
        """M11-A02: Uso de filtros restringe a busca aos tipos selecionados."""
        # 'Lavanda' está no produto e na referência visual
        res_only_product = self.search.search('Lavanda', entity_types=['product'])
        self.assertTrue(all(r.entity_type == 'product' for r in res_only_product))

        res_only_campaign = self.search.search('Sensorial', entity_types=['campaign'])
        self.assertTrue(all(r.entity_type == 'campaign' for r in res_only_campaign))

        res_multi = self.search.search('de', entity_types=['idea', 'template'])
        self.assertTrue(all(r.entity_type in ('idea', 'template') for r in res_multi))

    def test_relevance_scoring_ranking(self):
        """M11-A02: Correspondência exata em título possui score mais alto que correspondência parcial em detalhes."""
        results = self.search.search('Vela Aromática')
        self.assertGreater(len(results), 0)
        # O primeiro item deve ser o produto cujo título casa exatamente
        self.assertEqual(results[0].title, 'Vela Aromática de Lavanda & Cedro')
        self.assertGreater(results[0].score, 80.0)


if __name__ == '__main__':
    unittest.main()
