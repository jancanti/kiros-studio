"""Testes unitários para Memória Tipada, recuperação seletiva, compactação e conflitos (M03-A02, M03-A05, M03-A06)."""
from pathlib import Path
import tempfile
import unittest

from kiros.application import Application
from kiros.core.contracts import Provenance
from kiros.director.memory import VALID_MEMORY_TYPES, ConflictReport, MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.memory = self.app.memory
        self.director = self.app.director
        self.library = self.app.library

    def provenance(self, ref='teste-memoria'):
        return Provenance('user', ref, '2026-09-12T12:00:00+00:00')

    def test_six_valid_memory_types_and_rejection_of_invalid(self):
        # M03-A05, Seção 48: Tipos: campaign_context, recurring_preference, brand_rule, commercial_data, creative_decision, operational_setting
        expected_types = {
            'campaign_context',
            'recurring_preference',
            'brand_rule',
            'commercial_data',
            'creative_decision',
            'operational_setting',
        }
        self.assertEqual(set(VALID_MEMORY_TYPES), expected_types)

        prov = self.provenance()
        for m_type in VALID_MEMORY_TYPES:
            mem_id = self.memory.store_memory(
                memory_type=m_type,
                key=f'key_{m_type}',
                value=f'Valor teste para {m_type}',
                scope='global',
                confidence=0.95,
                provenance=prov,
            )
            self.assertTrue(bool(mem_id))

        # Rejeita tipo inexistente
        with self.assertRaises(ValueError) as ctx:
            self.memory.store_memory('invalid_type', 'k', 'v')
        self.assertIn('Tipo de memória inválido', str(ctx.exception))

        # Rejeita chave vazia
        with self.assertRaises(ValueError) as ctx:
            self.memory.store_memory('brand_rule', '   ', 'v')
        self.assertIn('não pode ser vazia', str(ctx.exception))

    def test_selective_retrieval_and_provenance(self):
        # M03-A05: Não carregar toda memória em toda chamada; recuperação seletiva
        prov1 = Provenance('user', 'briefing-1', '2026-09-12T12:00:00+00:00')
        prov2 = Provenance('automatic_analysis', 'analytics-1', '2026-09-12T12:05:00+00:00')

        self.memory.store_memory('brand_rule', 'palette_restriction', 'Não usar cores fluorescentes', scope='brand', provenance=prov1)
        self.memory.store_memory('recurring_preference', 'visual_mood', 'Minimalismo nórdico e acolhedor', scope='campaign', provenance=prov1)
        self.memory.store_memory('commercial_data', 'best_seller', 'Vela Bergamota', scope='sales', provenance=prov2)

        # Recupera somente brand_rule
        brand_mems = self.memory.query_memories(memory_types=['brand_rule'])
        self.assertEqual(len(brand_mems), 1)
        self.assertEqual(brand_mems[0]['key'], 'palette_restriction')
        self.assertEqual(brand_mems[0]['provenance'], 'user')

        # Recupera somente por chave específica
        key_mems = self.memory.query_memories(keys=['best_seller'])
        self.assertEqual(len(key_mems), 1)
        self.assertEqual(key_mems[0]['value'], 'Vela Bergamota')
        self.assertEqual(key_mems[0]['provenance'], 'automatic_analysis')

        # Não carrega tudo quando filtro é restrito
        filtered = self.memory.retrieve_relevant_context(memory_types=['recurring_preference'])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['key'], 'visual_mood')

    def test_memory_compaction_and_budget(self):
        # M03-A05, M03-A06: Compactação de memória tipada
        long_val = "Texto extenso com múltiplos espaços e redundâncias desnecessárias para teste de compactação de contexto da KIROS Studio."
        self.memory.store_memory('brand_rule', 'long_rule', long_val, provenance=self.provenance())
        self.memory.store_memory('operational_setting', 'tone_pref', '   Sofisticado   e   calmo   ', provenance=self.provenance())

        mems = self.memory.query_memories(limit=10)
        compacted = self.memory.compact_memories(mems, max_chars=120)

        self.assertIn('tone_pref', compacted)
        self.assertEqual(compacted['tone_pref']['value'], 'Sofisticado e calmo')  # Espaços normalizados
        self.assertEqual(compacted['tone_pref']['type'], 'operational_setting')
        self.assertIn('provenance', compacted['tone_pref'])

        # Orçamento restrito trunca valores longos
        self.assertIn('long_rule', compacted)
        self.assertTrue(len(compacted['long_rule']['value']) <= 60)
        self.assertTrue(compacted['long_rule']['value'].endswith('...'))

    def test_conflict_detection_and_non_overwriting_of_official_data(self):
        # M03-A05, Seção 49: Conflitos mostram origens, recomendações e nunca sobrescrevem dados oficiais
        official_brand = {
            'colors': 'Tons terrosos, bege linho e preto carvão',
            'voice': 'Sofisticado, acolhedor e contemplativo',
            'values': 'Autenticidade, rituais e bem-estar',
        }
        official_product = {
            'id': 'vela-alecrim',
            'name': 'Vela Alecrim',
            'attributes': {
                'fragrance_notes': {'value': 'Alecrim, eucalipto e cedro', 'protection': 'critical'},
                'finish': {'value': 'Vidro fosco âmbar', 'protection': 'protected'},
                'mood_vibe': {'value': 'Energizante', 'protection': 'free'},
            },
        }

        # Candidato propõe dados conflitantes com a Brand Bible e Product Bible
        candidate_data = {
            'colors': 'Neon magenta e verde limão vibrante',  # Conflito crítico com Brand Bible
            'fragrance_notes': 'Baunilha doce com canela',    # Conflito crítico com Product Bible
            'finish': 'Lata de alumínio pintada de branco',    # Conflito protegido com Product Bible
            'mood_vibe': 'Relaxante noturno',                 # Conflito free
        }

        conflicts = self.memory.detect_conflicts(
            candidate_data=candidate_data,
            official_brand=official_brand,
            official_product=official_product,
            candidate_source='briefing_livre_usuario',
        )

        self.assertEqual(len(conflicts), 4)

        # 1. Conflito com Brand Bible
        brand_conf = next(c for c in conflicts if c.field == 'brand.colors')
        self.assertTrue(brand_conf.is_high_impact)
        self.assertEqual(brand_conf.official_source, 'brand_bible')
        self.assertEqual(brand_conf.candidate_source, 'briefing_livre_usuario')
        self.assertEqual(brand_conf.official_value, official_brand['colors'])
        self.assertEqual(brand_conf.candidate_value, candidate_data['colors'])
        self.assertIn('Manter diretriz oficial', brand_conf.recommendation)

        # 2. Conflito crítico com Product Bible
        crit_conf = next(c for c in conflicts if c.field == 'product.fragrance_notes')
        self.assertTrue(crit_conf.is_high_impact)
        self.assertEqual(crit_conf.official_source, 'product_bible')
        self.assertIn('não pode ser alterado automaticamente', crit_conf.recommendation)

        # 3. Conflito livre com Product Bible
        free_conf = next(c for c in conflicts if c.field == 'product.mood_vibe')
        self.assertFalse(free_conf.is_high_impact)
        self.assertIn('Permitir variação criativa', free_conf.recommendation)

        # 4. Prova cabal de NÃO sobrescrita: dados oficiais continuam 100% inalterados
        self.assertEqual(official_brand['colors'], 'Tons terrosos, bege linho e preto carvão')
        self.assertEqual(official_product['attributes']['fragrance_notes']['value'], 'Alecrim, eucalipto e cedro')

    def test_creative_director_consults_brand_product_and_memory(self):
        # M03-A02: Creative Director consulta marca, produto e memória relevante por interfaces
        brand_prop = self.library.propose('brand', 'global', {
            'colors': 'Tons terrosos e âmbar',
            'fonts': 'Cormorant Garamond e Inter',
        }, source='Definição de marca oficial')
        self.library.approve(brand_prop, approver='Diretoria de Marca')

        self.library.create_product('difusor-lavanda', 'Difusor de Varetas Lavanda & Cedro', source='catalogo')
        prod_prop = self.library.propose('product', 'difusor-lavanda', {
            'glass': {'value': 'Vidro fosco âmbar 250ml', 'protection': 'critical'},
            'cap': {'value': 'Tampa de madeira nobre torneada', 'protection': 'protected'},
        }, source='Definição de atributos oficiais')
        self.library.approve(prod_prop, approver='Gerente de Produto')

        self.memory.store_memory('brand_rule', 'tone_rule', 'Não usar gírias ou superlativos agressivos', provenance=self.provenance())

        # Consulta via interface do CreativeDirector
        context = self.director.consult_relevant_context(
            brand_keys=['colors', 'fonts'],
            product_id='difusor-lavanda',
            product_fields=['glass', 'cap'],
            memory_types=['brand_rule'],
        )

        self.assertIn('brand', context)
        self.assertEqual(context['brand']['colors'], 'Tons terrosos e âmbar')
        self.assertIn('product', context)
        self.assertIn('glass', context['product'])
        self.assertEqual(context['product']['glass']['value'], 'Vidro fosco âmbar 250ml')
        self.assertIn('memories', context)
        self.assertIn('tone_rule', context['memories'])


if __name__ == '__main__':
    unittest.main()
