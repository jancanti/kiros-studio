"""Testes unitários para economia de tokens, contexto seletivo e deduplicação (M02-A06, Seções 25 e 77)."""
from pathlib import Path
import tempfile
import unittest

from kiros.application import Application
from kiros.context import ContextOptimizer
from kiros.cost import UnknownPricingError


class TokenEconomyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.optimizer = self.app.context_optimizer

    def test_selective_brand_retrieval_never_sends_full_knowledge_base(self):
        # M02-A06 e Seção 77: nunca enviar toda a base por padrão; recuperar somente a informação necessária
        full_brand_bible = {
            'colors': 'Verde floresta profundo #273b32, papel suave #f5f3ee, sálvia #e5eade',
            'typography': 'Títulos em Georgia, navegação em Arial',
            'voice': 'Antigo chique, novo moderno, tom acolhedor e poético sem gírias',
            'values': 'Intenção antes da criação, desaceleração, aconchego olfativo',
            'history': 'Fundada em Sorocaba com inspiração em aromas botânicos naturais e memória afetiva familiar...',
            'unrelated_notes': 'Anotações internas de testes que não devem ser enviadas...',
        }

        # Para geração visual, precisamos apenas de cores e tipografia
        selective = ContextOptimizer.select_brand_context(full_brand_bible, ['colors', 'typography'])
        self.assertEqual(set(selective.keys()), {'colors', 'typography'})
        self.assertNotIn('history', selective)
        self.assertNotIn('unrelated_notes', selective)

    def test_selective_product_retrieval(self):
        full_product_attributes = {
            'name': {'value': 'Vela Alecrim & Flor de Laranjeira', 'protection': 'critical'},
            'material': {'value': 'Vidro fosco âmbar com tampa de madeira', 'protection': 'protected'},
            'wax': {'value': 'Cera vegetal de coco e palma', 'protection': 'protected'},
            'wick': {'value': 'Pavio 100% algodão trançado', 'protection': 'free'},
            'aroma_notes': {'value': 'Topo: alecrim, Corpo: flor de laranjeira, Fundo: âmbar', 'protection': 'critical'},
            'internal_sku': {'value': 'SKU-998822-INT', 'protection': 'free'},
        }

        # Para o slide de ambientação, recuperamos apenas material e aroma
        selective = ContextOptimizer.select_product_context(full_product_attributes, ['material', 'aroma_notes'])
        self.assertEqual(set(selective.keys()), {'material', 'aroma_notes'})
        self.assertEqual(selective['material']['value'], 'Vidro fosco âmbar com tampa de madeira')
        self.assertEqual(selective['material']['protection'], 'protected')
        self.assertNotIn('internal_sku', selective)

    def test_compact_context_and_budget_enforcement(self):
        # M02-A06: contexto compacto e orçamento
        verbose_context = {
            'brand': {'colors': '  Verde    #273b32   \n  \t   ', 'empty_field': None},
            'scene': '   Ambiente   quente de   sala de estar   com iluminação   natural suave   ',
            'unused': '',
        }
        compacted = ContextOptimizer.compact_context(verbose_context)
        self.assertEqual(compacted['brand']['colors'], 'Verde #273b32')
        self.assertEqual(compacted['scene'], 'Ambiente quente de sala de estar com iluminação natural suave')
        self.assertNotIn('empty_field', compacted['brand'])
        self.assertNotIn('unused', compacted)

        # Orçamento restrito: força truncamento seguro se exceder limite
        large_context = {
            'name': 'Produto KIROS',
            'description': 'Um texto extremamente longo que detalha de forma excessivamente minuciosa cada um dos micro aspectos da composição estética do frasco de vidro fosco...',
        }
        bounded = ContextOptimizer.enforce_context_budget(large_context, max_chars=160)
        self.assertTrue(bounded.get('context_truncated'))
        self.assertTrue(bounded['description'].endswith('...'))

        # Limite ainda mais estrito corta campos não críticos
        extreme = ContextOptimizer.enforce_context_budget(large_context, max_chars=60)
        self.assertIn('name', extreme)
        self.assertNotIn('description', extreme)

    def test_cache_deduplication_and_invalidation(self):
        # M02-A06: cache com invalidação e deduplicação evitam chamadas redundantes
        opt = self.optimizer
        ctx = {'colors': 'verde', 'material': 'vidro'}
        key1 = opt.compute_cache_key('image_prompt', 'Vela aromática', ctx)
        key2 = opt.compute_cache_key('image_prompt', 'Vela aromática', ctx)
        self.assertEqual(key1, key2)  # Deduplicação determinística

        # Grava no cache com tag da entidade 'brand'
        opt.set_cached(key1, 'prompt_otimizado_simulado', entity_tags=['brand'])
        self.assertEqual(opt.get_cached(key1), 'prompt_otimizado_simulado')

        # Atualização da marca invalida entradas associadas
        invalidated_count = opt.invalidate_entity('brand')
        self.assertEqual(invalidated_count, 1)
        self.assertIsNone(opt.get_cached(key1))

    def test_failure_or_unknown_price_rejects_spend(self):
        # M02-A06: falha ou preço desconhecido não autoriza gasto
        # Preço conhecido para Imagen 3 oficial autoriza
        cost = self.optimizer.authorize_spend('gemini', 'imagen-3.0-generate-002', count=1)
        self.assertEqual(cost, 0.030)

        # Provedor ou modelo inexistente ou sem custo rejeita gasto
        with self.assertRaises(UnknownPricingError):
            self.optimizer.authorize_spend('custom', 'unknown-model-xyz')

        with self.assertRaises(UnknownPricingError):
            self.optimizer.authorize_spend('gemini', 'nonexistent-model')


if __name__ == '__main__':
    unittest.main()
