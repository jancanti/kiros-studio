import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from kiros.application import Application
from kiros.core.contracts import Provenance
from kiros.core.director import CreativeDirector
from kiros.infrastructure.local import FileStorage, SQLiteDatabase
from kiros.infrastructure.security import ExternalGateway, Policy, Secret


class FoundationTests(unittest.TestCase):
    def test_mock_refuses_every_external_operation_before_transport(self):
        for paid in (False, True):
            for publish in (False, True):
                transport = Mock()
                with self.assertRaises(PermissionError):
                    ExternalGateway(Policy('mock', True, True)).call(
                        transport, paid=paid, publish=publish, approved=True)
                transport.assert_not_called()

    def test_live_requires_flags_and_specific_approval(self):
        for policy, options in [(Policy('live'), {'approved': True}),
                                (Policy('live', True, True), {}),
                                (Policy('live', True), {'publish': True, 'approved': True})]:
            transport = Mock()
            with self.assertRaises(PermissionError):
                ExternalGateway(policy).call(transport, **options)
            transport.assert_not_called()
        self.assertEqual(ExternalGateway(Policy('live', True)).call(lambda: 42, approved=True), 42)

    def test_environment_defaults_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Policy.from_env(), Policy())
        with patch.dict(os.environ, {'KIROS_PROVIDER_MODE': 'typo'}):
            with self.assertRaises(ValueError):
                Policy.from_env()

    def test_secret_and_provider_error_are_not_exposed(self):
        secret = Secret('private-example-key')
        self.assertNotIn(secret.value, repr(secret) + str(secret))
        def failing():
            raise ValueError(secret.value)
        with self.assertRaises(RuntimeError) as caught:
            ExternalGateway(Policy('live', True)).call(failing, approved=True)
        self.assertNotIn(secret.value, str(caught.exception))
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'EXAMPLE_API_KEY': secret.value}):
                self.assertNotIn(secret.value, json.dumps(Application(Path(directory)).status()))

    def test_provenance_requires_known_source_reference_and_timezone(self):
        for values in [('invented', 'x', '2026-09-12T00:00:00+00:00'),
                       ('user', '', '2026-09-12T00:00:00+00:00'),
                       ('user', 'x', '2026-09-12T00:00:00')]:
            with self.assertRaises(ValueError):
                Provenance(*values)

    def test_sqlite_reopen_migration_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'studio.sqlite3'
            origin = Provenance('user', 'test.input', '2026-09-12T00:00:00+00:00')
            SQLiteDatabase(path).set_preference('workspace_name', 'KIROS teste', origin)
            self.assertEqual(SQLiteDatabase(path).get_preference('workspace_name'), 'KIROS teste')
            with sqlite3.connect(path) as db:
                self.assertEqual({r[0] for r in db.execute('SELECT version FROM schema_migrations')},
                                 {'001_preferences.sql', '002_library.sql', '003_providers_and_costs.sql', '004_creative_director_and_ideas.sql', '005_campaigns_storyboard_and_approval.sql', '006_execution_queue_and_monitoring.sql', '007_fidelity_and_versioning.sql', '008_layout_and_templates.sql', '009_copy_and_stories.sql', '010_calendar_and_instagram.sql', '011_insights_and_experiments.sql', '012_learning_prompts_and_search.sql'})
                self.assertEqual(db.execute('SELECT source, reference FROM preferences').fetchone(), ('user', 'test.input'))
                self.assertNotIn('BLOB', db.execute("SELECT sql FROM sqlite_master WHERE name='preferences'").fetchone()[0])

    def test_files_persist_and_reject_escape_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'files'
            storage = FileStorage(root)
            storage.put('fixtures/sample.txt', b'deterministic local fixture')
            self.assertEqual(FileStorage(root).get('fixtures/sample.txt'), b'deterministic local fixture')
            (root / 'escape').symlink_to(Path(directory), target_is_directory=True)
            for key in ('../outside', '/tmp/outside', 'escape/outside', 'a/../../outside', '', '.', 'a\\b'):
                with self.assertRaises(ValueError):
                    storage.put(key, b'forbidden')
                with self.assertRaises(ValueError):
                    storage.get(key)
            self.assertFalse((Path(directory) / 'outside').exists())

    def test_director_provider_can_be_replaced(self):
        provider = Mock()
        provider.complete.return_value = 'alternate local provider'
        self.assertEqual(CreativeDirector(provider).connection_preview(), 'alternate local provider')
        provider.complete.assert_called_once_with('connection_preview')

    def test_workspace_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Application(Path(directory))
            for invalid in ('', ' ' * 5, 'x' * 81, None):
                with self.assertRaises(ValueError):
                    app.rename_workspace(invalid)
            app.rename_workspace(' KIROS teste ')
            self.assertEqual(app.status()['workspace_name'], 'KIROS teste')


if __name__ == '__main__':
    unittest.main()
