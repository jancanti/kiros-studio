"""Testes do Editor Visual Semântico e Proteção por Atributos (Seção 29 e Critérios M07-A02, M07-A03)."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from kiros.infrastructure.local import SQLiteDatabase, FileStorage
from kiros.layout.editor import LayoutEditor
from kiros.layout.engine import LayoutEngine
from kiros.layout.models import (
    FORMAT_4_5,
    FORMAT_9_16,
    PROTECTION_FREE,
    PROTECTION_PROTECTED,
    PROTECTION_CRITICAL,
    ProtectedAttributeError,
    CriticalAttributeLockedError,
    LayoutValidationError,
)
from kiros.library import Library
from kiros.providers.mock import MockVision


class LayoutEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_path = Path(self.temp_dir.name)
        self.db = SQLiteDatabase(self.data_path / 'studio.sqlite3')
        self.storage = FileStorage(self.data_path / 'files')
        self.library = Library(self.db, self.storage, MockVision())
        self.engine = LayoutEngine()
        self.editor = LayoutEditor(self.db, self.engine, self.library)

        # Insere campanha e slide de teste
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO campaigns (id, title, briefing_json, strategy_json, products_json, approval_mode, status, plan_version, created_at, updated_at, provenance)
                   VALUES ('camp-test', 'Campanha Layout', '{}', '{}', '[]', 'minimal', 'draft', 1, '2026-09-12T10:00:00Z', '2026-09-12T10:00:00Z', 'test')'''
            )
            conn.execute(
                '''INSERT INTO storyboard_slides (id, campaign_id, slide_order, title, visual_prompt, framing, caption_draft, status, created_at, updated_at)
                   VALUES ('slide-test-1', 'camp-test', 1, 'Frasco com Chama', 'Prompt visual inicial', 'medium', 'Legenda inicial', 'draft', '2026-09-12T10:00:00Z', '2026-09-12T10:00:00Z')'''
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_green_free_attributes_update_without_confirmation(self):
        """M07-A02: Atributos verdes (posição, escala, enquadramento, iluminação) alteram livremente."""
        layout = self.editor.get_or_create_layout('camp-test', 'slide-test-1', target_format=FORMAT_4_5)

        updates = {
            'position_x': 120,
            'position_y': 60,
            'scale': 1.25,
            'framing': 'close-up',
            'lighting': 'golden_hour',
        }

        updated, messages = self.editor.update_layout(layout.id, updates)

        self.assertEqual(updated.image.position_x, 120)
        self.assertEqual(updated.image.position_y, 60)
        self.assertEqual(updated.image.scale, 1.25)
        self.assertEqual(updated.image.framing, 'close-up')
        self.assertEqual(updated.image.lighting, 'golden_hour')

        # Persistência no SQLite
        reloaded = self.editor.get_layout(layout.id)
        self.assertEqual(reloaded.image.framing, 'close-up')
        self.assertEqual(reloaded.image.lighting, 'golden_hour')

    def test_yellow_protected_attributes_require_confirmation(self):
        """M07-A02: Atributos amarelos (protected: textos exatos, tipografia, cores) exigem confirmação explícita."""
        layout = self.editor.get_or_create_layout('camp-test', 'slide-test-1')

        # Tentativa 1: Sem confirm_protected -> deve falhar com ProtectedAttributeError
        with self.assertRaises(ProtectedAttributeError) as ctx:
            self.editor.update_layout(
                layout.id,
                {'headline_text': 'Nova Frase Protegida'},
                confirm_protected=False,
            )
        self.assertIn("exige confirmação explícita", str(ctx.exception))

        # Tentativa 2: Com confirm_protected=True -> sucesso
        updated, msgs = self.editor.update_layout(
            layout.id,
            {'headline_text': 'Nova Frase Protegida', 'cta_text': 'Compre Agora'},
            confirm_protected=True,
        )
        self.assertEqual(updated.headline.text, 'Nova Frase Protegida')
        self.assertEqual(updated.cta.text, 'Compre Agora')
        self.assertTrue(any('protegido' in m for m in msgs))

    def test_red_critical_attributes_require_audit_unlock_and_log_exception(self):
        """M07-A02: Atributos vermelhos (critical: logo_locked, aspect_ratio) exigem unlock explícito auditado."""
        layout = self.editor.get_or_create_layout('camp-test', 'slide-test-1')

        # Tentativa 1: Sem unlock_critical -> bloqueado
        with self.assertRaises(CriticalAttributeLockedError) as ctx:
            self.editor.update_layout(
                layout.id,
                {'logo_locked': False},
                unlock_critical=False,
            )
        self.assertIn("está bloqueado. Exige autorização explícita", str(ctx.exception))

        # Tentativa 2: Com unlock_critical mas sem justificativa formal -> bloqueado
        with self.assertRaises(CriticalAttributeLockedError) as ctx:
            self.editor.update_layout(
                layout.id,
                {'logo_locked': False},
                unlock_critical=True,
                audit_reason='',
                unlocked_by='',
            )
        self.assertIn("obrigatório fornecer justificativa formal", str(ctx.exception))

        # Tentativa 3: Com unlock_critical, justificativa formal e identificação do responsável -> sucesso com log
        updated, msgs = self.editor.update_layout(
            layout.id,
            {'logo_locked': False},
            unlock_critical=True,
            audit_reason='Exceção aprovada para campanha especial em banner vertical',
            unlocked_by='Diretoria de Arte · João Silva',
        )
        self.assertFalse(updated.logo.aspect_ratio_locked)

        # Comprova gravação no log de auditoria (layout_audit_log)
        audit_logs = self.editor.list_audit_entries(layout_id=layout.id)
        self.assertEqual(len(audit_logs), 1)
        entry = audit_logs[0]
        self.assertEqual(entry.attribute_name, 'logo_locked')
        self.assertEqual(entry.protection_level, PROTECTION_CRITICAL)
        self.assertEqual(entry.previous_value, 'True')
        self.assertEqual(entry.new_value, 'False')
        self.assertEqual(entry.reason, 'Exceção aprovada para campanha especial em banner vertical')
        self.assertEqual(entry.operator, 'Diretoria de Arte · João Silva')

    def test_product_bible_is_never_modified_by_layout_editing(self):
        """M07-A03: Edição nunca muda Product Bible oficial automaticamente; bloqueio validado no servidor."""
        # 1. Configura uma Product Bible oficial com versão aprovada via Library
        self.library.create_product('vela-lavanda', 'Vela de Lavanda Francesa')
        initial_bible = {
            'shape': {'value': 'cilíndrico clássico', 'protection': 'free'},
            'proportion': {'value': 'altura 9cm, diâmetro 7cm', 'protection': 'protected'},
            'material': {'value': 'vidro âmbar espesso', 'protection': 'critical'},
            'glass': {'value': 'âmbar translúcido', 'protection': 'critical'},
            'cap': {'value': 'madeira de reflorestamento com gravação', 'protection': 'critical'},
            'label': {'value': 'papel linho 180g texturizado', 'protection': 'critical'},
            'logo': {'value': 'KIROS gravado em serigrafia preta', 'protection': 'critical'},
            'colors': {'value': 'âmbar e verde sálvia', 'protection': 'free'},
            'packaging': {'value': 'cartucho kraft biodegradável', 'protection': 'free'},
        }
        prop_id = self.library.propose('product', 'vela-lavanda', initial_bible, 'Ficha inicial do produto')
        self.library.approve(prop_id, 'Gerência de Marca')

        # Snapshot da versão oficial aprovada antes de qualquer edição de layout
        conn_pre = sqlite3.connect(self.db.path)
        conn_pre.row_factory = sqlite3.Row
        official_before = self.library._official(conn_pre, 'product', 'vela-lavanda')
        conn_pre.close()
        self.assertIsNotNone(official_before)
        version_before = official_before['version']
        content_before = official_before['content']
        approved_at_before = official_before['approved_at']

        # 2. Executa múltiplas edições e mutações de layout no slide
        layout = self.editor.get_or_create_layout('camp-test', 'slide-test-1')
        self.editor.update_layout(
            layout.id,
            {'position_x': 50, 'scale': 1.1, 'framing': 'detail', 'lighting': 'dramatic'},
        )
        self.editor.update_layout(
            layout.id,
            {'headline_text': 'Aroma Refinado de Lavanda', 'cta_text': 'Compre Agora'},
            confirm_protected=True,
        )
        self.editor.switch_format(layout.id, FORMAT_9_16)
        self.editor.approve_layout(layout.id, approved_by='Diretoria de Criação')

        # 3. Tentativa de injetar atualização na Product Bible via editor de layout -> sumariamente rejeitada
        with self.assertRaises(LayoutValidationError) as ctx:
            self.editor.update_layout(
                layout.id,
                {'product_bible': {'material': 'plástico descartável'}},
            )
        self.assertIn("nunca altera a Product Bible oficial", str(ctx.exception))

        # 4. Comprova no SQLite que a Product Bible oficial está 100% INTACTA
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            official_after = self.library._official(conn, 'product', 'vela-lavanda')
            all_versions_count = conn.execute(
                'SELECT COUNT(*) FROM bible_versions WHERE kind="product" AND owner="vela-lavanda"'
            ).fetchone()[0]

        self.assertEqual(all_versions_count, 1)  # Nenhuma versão nova foi criada
        self.assertEqual(official_after['version'], version_before)
        self.assertEqual(official_after['content'], content_before)
        self.assertEqual(official_after['approved_at'], approved_at_before)


if __name__ == '__main__':
    unittest.main()
