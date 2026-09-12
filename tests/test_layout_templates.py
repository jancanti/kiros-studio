"""Testes da Biblioteca de Templates e Governança de Layout (Seção 30 e Critério M07-A04)."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from kiros.infrastructure.local import SQLiteDatabase
from kiros.layout.editor import LayoutEditor
from kiros.layout.engine import LayoutEngine
from kiros.layout.models import (
    FORMAT_4_5,
    FORMAT_9_16,
    TEMPLATE_ACTIVE,
    TEMPLATE_ARCHIVED,
    TEMPLATE_EXPERIMENTAL,
    FAMILY_EDITORIAL_MINIMALIST,
    FAMILY_LIFESTYLE_NATURAL,
    FAMILY_SPLIT_BALANCED,
    FAMILY_BOLD_MODERN,
    ExperimentalTemplateUnauthorizedError,
    LayoutValidationError,
)
from kiros.layout.templates import TemplateLibrary


class LayoutTemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_path = Path(self.temp_dir.name)
        self.db = SQLiteDatabase(self.data_path / 'studio.sqlite3')
        self.engine = LayoutEngine()
        self.editor = LayoutEditor(self.db, self.engine)
        self.templates = TemplateLibrary(self.db)

        # Insere dados de campanha e slides para testes
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO campaigns (id, title, briefing_json, strategy_json, products_json, approval_mode, status, plan_version, created_at, updated_at, provenance)
                   VALUES ('camp-tpl', 'Campanha Templates', '{}', '{}', '[]', 'minimal', 'draft', 1, '2026-09-12T10:00:00Z', '2026-09-12T10:00:00Z', 'test')'''
            )
            for i in range(1, 5):
                conn.execute(
                    '''INSERT INTO storyboard_slides (id, campaign_id, slide_order, title, visual_prompt, framing, caption_draft, status, created_at, updated_at)
                       VALUES (?, 'camp-tpl', ?, 'Slide Tpl', 'Prompt', 'medium', 'Legenda', 'draft', '2026-09-12T10:00:00Z', '2026-09-12T10:00:00Z')''',
                    (f'slide-tpl-{i}', i),
                )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_seeded_templates_and_families(self):
        """M07-A04: Comprova existência de templates nas famílias aprovadas (Seção 30)."""
        all_tpls = self.templates.list_templates()
        self.assertGreaterEqual(len(all_tpls), 4)

        families = {t.family for t in all_tpls}
        self.assertIn(FAMILY_EDITORIAL_MINIMALIST, families)
        self.assertIn(FAMILY_LIFESTYLE_NATURAL, families)
        self.assertIn(FAMILY_SPLIT_BALANCED, families)
        self.assertIn(FAMILY_BOLD_MODERN, families)

        # Filtragem por família e status
        min_tpls = self.templates.list_templates(family=FAMILY_EDITORIAL_MINIMALIST)
        self.assertTrue(len(min_tpls) >= 1)
        self.assertEqual(min_tpls[0].status, TEMPLATE_ACTIVE)

    def test_experimental_template_requires_explicit_authorization(self):
        """M07-A04: Templates experimentais exigem autorização; bloqueia aplicação sem flag explícita."""
        layout = self.editor.get_or_create_layout('camp-tpl', 'slide-tpl-1')

        # Template experimental padrão
        exp_tpl = self.templates.get_template('tpl-experimental-botanical')
        self.assertIsNotNone(exp_tpl)
        self.assertEqual(exp_tpl.status, TEMPLATE_EXPERIMENTAL)

        # Tentativa 1: Sem autorização explícita -> Erro de permissão
        with self.assertRaises(ExperimentalTemplateUnauthorizedError) as ctx:
            self.templates.apply_template(exp_tpl.id, layout, experimental_authorized=False)
        self.assertIn("exige autorização explícita", str(ctx.exception))

        # Tentativa 2: Com experimental_authorized=True -> Aplicação bem sucedida
        applied = self.templates.apply_template(exp_tpl.id, layout, experimental_authorized=True)
        self.assertEqual(applied.template_id, exp_tpl.id)
        self.assertEqual(applied.image.framing, 'overhead')
        self.assertEqual(applied.headline.font_size, 60)

    def test_overuse_detection_triggers_warning_and_recommends_diversity(self):
        """M07-A04: Comprova detecção de sobreuso quando template ultrapassa limiar recente (Seção 30 e 32)."""
        tpl_id = 'tpl-editorial-minimalist'

        # Aplica o mesmo template em 3 slides diferentes da campanha
        for i in range(1, 4):
            lay = self.editor.get_or_create_layout('camp-tpl', f'slide-tpl-{i}')
            self.templates.apply_template(tpl_id, lay)

        # Avalia detecção de sobreuso
        overuse = self.templates.detect_overuse(tpl_id, threshold_ratio=0.35)
        self.assertTrue(overuse['is_overused'])
        self.assertGreaterEqual(overuse['template_usage_count'], 3)
        self.assertIn('Alerta de sobreuso', overuse['warning'])
        self.assertTrue(len(overuse['recommended_families']) >= 1)

    def test_save_approved_composition_as_new_template(self):
        """M07-A04: Salva composição aprovada como novo template na biblioteca."""
        layout = self.editor.get_or_create_layout('camp-tpl', 'slide-tpl-1')
        layout, _ = self.editor.update_layout(
            layout.id,
            {'position_x': 100, 'framing': 'close-up', 'lighting': 'golden_hour'},
        )
        layout, _ = self.editor.update_layout(
            layout.id,
            {'headline_text': 'Aroma Dourado de Figo', 'cta_text': 'Experimente'},
            confirm_protected=True,
        )
        layout = self.editor.approve_layout(layout.id, approved_by='Diretoria de Criação')

        new_tpl = self.templates.save_composition_as_template(
            layout=layout,
            name='Figo & Madeira Âmbar',
            family=FAMILY_LIFESTYLE_NATURAL,
            status=TEMPLATE_ACTIVE,
        )

        self.assertTrue(new_tpl.id.startswith('tpl-custom-'))
        self.assertEqual(new_tpl.name, 'Figo & Madeira Âmbar')
        self.assertEqual(new_tpl.family, FAMILY_LIFESTYLE_NATURAL)
        self.assertEqual(new_tpl.status, TEMPLATE_ACTIVE)

        # Comprova que o novo template pode ser listado e aplicado a outro slide
        other_layout = self.editor.get_or_create_layout('camp-tpl', 'slide-tpl-2')
        applied = self.templates.apply_template(new_tpl.id, other_layout)
        self.assertEqual(applied.template_id, new_tpl.id)
        self.assertEqual(applied.image.framing, 'close-up')
        self.assertEqual(applied.image.lighting, 'golden_hour')

    def test_archived_template_cannot_be_applied(self):
        """M07-A04: Template arquivado é impedido de ser aplicado a novas composições."""
        tpl_id = 'tpl-bold-modern'
        self.templates.archive_template(tpl_id)

        archived_tpl = self.templates.get_template(tpl_id)
        self.assertEqual(archived_tpl.status, TEMPLATE_ARCHIVED)

        layout = self.editor.get_or_create_layout('camp-tpl', 'slide-tpl-1')
        with self.assertRaises(LayoutValidationError) as ctx:
            self.templates.apply_template(tpl_id, layout)
        self.assertIn("está arquivado", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
