"""Testes de Aprendizado, Sugestões de Regras e Prompt Library (M11-A01 e M11-A05)."""
from pathlib import Path
import tempfile
import unittest

from kiros.core.contracts import Provenance
from kiros.director.memory import MemoryStore
from kiros.infrastructure.local import SQLiteDatabase, FileStorage
from kiros.learning import LearningService, PromptLibrary
from kiros.library import Library
from kiros.providers.mock import MockVision


class LearningAndPromptsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        data_dir = Path(self.tmp.name)
        self.db = SQLiteDatabase(data_dir / 'studio.sqlite3')
        self.storage = FileStorage(data_dir / 'files')
        self.library = Library(self.db, self.storage, MockVision())
        self.memory = MemoryStore(self.db)
        self.learning = LearningService(self.db, self.library, self.memory)
        self.prompts = PromptLibrary(self.db)

        # Configura produto inicial
        self.library.create_product('prod-1', 'Vela Bergamota', 10, 'Cadastro teste')

    def test_campaign_corrections_generate_local_learning(self):
        """M11-A01: Correções geram aprendizado local; nenhuma alteração permanente automática."""
        # Cria campanha
        cid = 'camp-1'
        with self.db.path.open():
            with self.library.connection() as conn:
                conn.execute(
                    "INSERT INTO campaigns (id, title, briefing_json, strategy_json, products_json, created_at, updated_at, provenance) VALUES (?, ?, '{}', '{}', '[]', '2026-09-12T12:00:00Z', '2026-09-12T12:00:00Z', 'user')",
                    (cid, 'Lançamento Bergamota'),
                )

        # Registra correção local
        lid = self.learning.record_campaign_correction(
            campaign_id=cid,
            correction_note='Evitar sombras duras no frasco de vidro; preferir luz natural difusa.',
            slide_id='slide-1',
            source='revisao_arte',
        )
        self.assertTrue(bool(lid))

        learnings = self.learning.list_learnings(campaign_id=cid)
        self.assertEqual(len(learnings), 1)
        self.assertEqual(learnings[0]['id'], lid)
        self.assertIn('sombras duras', learnings[0]['correction_note'])
        self.assertIn('campaign_correction:revisao_arte', learnings[0]['provenance'])

        # Nenhuma Brand Bible ou Product Bible foi alterada automaticamente
        brand = self.library.brand_for()
        self.assertEqual(brand, {})

    def test_repeated_preferences_create_proposals_not_auto_applied(self):
        """M11-A01: Preferências repetidas geram propostas, não alterações automáticas."""
        cid1, cid2 = 'camp-10', 'camp-20'
        with self.library.connection() as conn:
            conn.execute("INSERT INTO campaigns (id, title, briefing_json, strategy_json, products_json, created_at, updated_at, provenance) VALUES (?, 'C1', '{}', '{}', '[]', '2026-09-12', '2026-09-12', 'u')", (cid1,))
            conn.execute("INSERT INTO campaigns (id, title, briefing_json, strategy_json, products_json, created_at, updated_at, provenance) VALUES (?, 'C2', '{}', '{}', '[]', '2026-09-12', '2026-09-12', 'u')", (cid2,))

        # Duas correções com o mesmo tema em campanhas diferentes
        self.learning.record_campaign_correction(cid1, 'Preferir fundo de madeira clara para difusores de ambiente')
        self.learning.record_campaign_correction(cid2, 'Preferir fundo de madeira clara para difusores de ambiente')

        proposals = self.learning.list_proposals(status='suggested')
        self.assertGreaterEqual(len(proposals), 1)
        prop = proposals[0]
        self.assertEqual(prop['kind'], 'recurring_preference')
        self.assertEqual(prop['status'], 'suggested')
        self.assertIsNone(prop['approved_by'])
        self.assertIsNone(prop['approved_at'])

    def test_approval_of_proposals_applies_permanently_with_approver_and_provenance(self):
        """M11-A01 e M11-A05: Aprovação formal aplica regra permanentemente registrando responsável."""
        # 1. Proposta de preferência repetida
        prop_id = self.learning.suggest_recurring_preference(
            key='estilo_madeira',
            value='Madeira nobre clara fosca',
            reason='Observado em múltiplos lançamentos de outono',
            provenance=Provenance('user', 'tendencia_outono', '2026-09-12T10:00:00+00:00'),
        )

        # Não aprovado: ainda não deve existir na memória tipada oficial
        mems = self.memory.query_memories(memory_types=['recurring_preference'], keys=['estilo_madeira'])
        self.assertEqual(len(mems), 0)

        # Tentativa sem aprovador deve falhar
        with self.assertRaises(ValueError):
            self.learning.approve_proposal(prop_id, '')

        # Aprovação formal
        approved = self.learning.approve_proposal(prop_id, approver='Diretora Criativa')
        self.assertEqual(approved['status'], 'approved')
        self.assertEqual(approved['approved_by'], 'Diretora Criativa')
        self.assertIsNotNone(approved['approved_at'])

        # Agora deve constar na memória oficial com proveniência
        mems = self.memory.query_memories(memory_types=['recurring_preference'], keys=['estilo_madeira'])
        self.assertEqual(len(mems), 1)
        self.assertEqual(mems[0]['provenance'], 'user')
        self.assertEqual(approved['approved_by'], 'Diretora Criativa')

        # Tentativa de aprovar novamente falha
        with self.assertRaises(ValueError):
            self.learning.approve_proposal(prop_id, 'Outro Aprovador')

    def test_prompt_library_suggestion_and_strict_approval_requirement(self):
        """M11-A01 e Seção 55: Prompts são sugeridos e só viram permanentes com aprovação."""
        prompt_id = self.prompts.suggest_prompt(
            title='Difusor Minimalista com Luz Suave',
            objective='Lançamento de difusor de varetas em ambiente sofisticado',
            engine='recraft_v3',
            context='Linha Casa Aromas · Ambiente de estar clean',
            prompt_text='Minimalist home fragrance diffuser, warm morning light, clean lines, luxury spa ambiance',
            result_summary='Excelente nitidez e leitura da etiqueta KIROS',
            performance_score=94.5,
            provenance=Provenance('automatic_analysis', 'slide_generation_run_12', '2026-09-12T10:00:00+00:00'),
        )

        # Inicialmente sugerido, não aprovado
        p = self.prompts.get_prompt(prompt_id)
        self.assertEqual(p['status'], 'suggested')
        self.assertIsNone(p['approved_by'])
        self.assertIsNone(p['approved_at'])

        suggested_list = self.prompts.list_prompts(status='suggested')
        self.assertEqual(len(suggested_list), 1)

        approved_list = self.prompts.list_prompts(status='approved')
        self.assertEqual(len(approved_list), 0)

        # Tentativa sem aprovador falha
        with self.assertRaises(ValueError):
            self.prompts.approve_prompt(prompt_id, '  ')

        # Aprovação formal
        approved_prompt = self.prompts.approve_prompt(prompt_id, approver='Diretor de Criação')
        self.assertEqual(approved_prompt['status'], 'approved')
        self.assertEqual(approved_prompt['approved_by'], 'Diretor de Criação')
        self.assertIsNotNone(approved_prompt['approved_at'])

        # Lista de aprovados atualizada
        approved_list = self.prompts.list_prompts(status='approved')
        self.assertEqual(len(approved_list), 1)
        self.assertEqual(approved_list[0]['id'], prompt_id)

    def test_brand_rule_and_product_change_proposals(self):
        """M11-A01: Propostas para Brand Bible e Product Bible exigem aprovação."""
        # 1. Brand rule proposal
        b_prop = self.learning.propose_brand_rule(
            rule_name='sem_plastico_visivel',
            rule_value='Nunca mostrar elementos plásticos brilhantes em fotos institucionais',
            reason='Reforçar posicionamento de sustentabilidade e luxo sensorial',
        )
        self.learning.approve_proposal(b_prop, approver='Head de Marca')
        mems = self.memory.query_memories(memory_types=['brand_rule'], keys=['sem_plastico_visivel'])
        self.assertEqual(len(mems), 1)

        # 2. Product change proposal
        p_prop = self.learning.propose_product_change(
            product_id='prod-1',
            attributes={'shape': {'value': 'Cilíndrico com vidro âmbar pesado', 'protection': 'protected'}},
            reason='Atualização de fornecedor de frascos',
        )
        approved_p = self.learning.approve_proposal(p_prop, approver='Gerente de Produto')
        self.assertEqual(approved_p['status'], 'approved')


if __name__ == '__main__':
    unittest.main()
