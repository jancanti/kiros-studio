"""Testes unitários e de integração para Backup e Restauração Consistente (M12-A01, Seção 71)."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

from kiros.application import Application
from kiros.backup import BackupService
from kiros.core.contracts import Provenance
from kiros.infrastructure.local import FileStorage, SQLiteDatabase


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = Path(self.tmp.name)
        self.app = Application(self.data_dir)
        self.backup_service = self.app.backup

        # Popula dados de teste para cobrir todos os escopos da Seção 71
        self._populate_test_data()

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def _populate_test_data(self):
        # 1. Marca e Produto
        self.app.library.propose('brand', 'global', {'colors': 'Verde Floresta e Âmbar', 'fonts': 'Rubik e Inter'}, 'user_test')
        self.app.library.create_product('vela-lavanda', 'Vela Aromática Lavanda', 50, 'user_test')

        # 2. Arquivo de asset no filesystem local
        self.app.storage.put('assets/test_photo.png', b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtestfixture')

        # 3. Campanha com slide
        cid = self.app.campaigns.create_campaign(
            title='Lançamento Primavera',
            briefing={'briefing_text': 'Aromas florais e sensação de renovação', 'custom_objective': 'lançamento'},
            strategy={'tone': 'floral'},
        )
        self.app.campaigns.add_storyboard_slide(cid, 'Slide Flor', 'Vela entre ramos de lavanda')

        # 4. Preferência e workspace
        self.app.rename_workspace('KIROS Espaço Matriz')

    def test_consistent_backup_creation_and_manifest(self):
        """M12-A01: Backup consistente de SQLite e arquivos inclui marca, produtos, campanhas, assets e configurações."""
        archive_path = self.backup_service.create_backup(name='backup_test_v1.zip')
        self.assertTrue(archive_path.exists())
        self.assertTrue(archive_path.is_file())

        with zipfile.ZipFile(archive_path, 'r') as zf:
            namelist = zf.namelist()
            self.assertIn('studio.sqlite3', namelist)
            self.assertIn('manifest.json', namelist)
            # Verifica que asset armazenado foi incluído
            self.assertTrue(any(name.startswith('files/') for name in namelist))

            manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
            self.assertEqual(manifest['version'], '1.0.0')
            self.assertTrue(bool(manifest['sqlite_sha256']))
            self.assertFalse(manifest['policy']['auto_delete_history'])
            self.assertTrue(manifest['policy']['atomic_snapshot'])

            # Estatísticas refletem dados reais
            stats = manifest['stats']
            self.assertGreaterEqual(stats.get('campaigns', 0), 1)
            self.assertGreaterEqual(stats.get('products', 0), 1)
            self.assertGreaterEqual(stats.get('slides', 0), 1)
            self.assertGreaterEqual(manifest.get('files_count', 0), 1)

    def test_restore_backup_without_deleting_or_overwriting_original(self):
        """M12-A01: Restauração testada em diretório alvo sem apagar o original e sem alterar dados existentes."""
        archive_path = self.backup_service.create_backup()

        with tempfile.TemporaryDirectory() as restore_tmp:
            target_dir = Path(restore_tmp) / 'restored_instance'

            report = self.backup_service.restore_backup(archive_path, target_dir)
            self.assertEqual(report['status'], 'success')
            self.assertEqual(report['sqlite_integrity'], 'ok')
            self.assertGreaterEqual(report['tables_count'], 10)
            self.assertGreaterEqual(report['restored_files_count'], 1)

            # Valida que o SQLite restaurado funciona perfeitamente
            restored_db = SQLiteDatabase(target_dir / 'studio.sqlite3')
            self.assertEqual(restored_db.get_preference('workspace_name'), 'KIROS Espaço Matriz')

            with sqlite3.connect(target_dir / 'studio.sqlite3') as conn:
                camp = conn.execute("SELECT title FROM campaigns WHERE title='Lançamento Primavera'").fetchone()
                self.assertIsNotNone(camp)
                prod = conn.execute("SELECT name FROM products WHERE id='vela-lavanda'").fetchone()
                self.assertIsNotNone(prod)

            # Valida que o asset foi recuperado intacto
            restored_storage = FileStorage(target_dir / 'files')
            self.assertEqual(restored_storage.get('assets/test_photo.png'), b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtestfixture')

            # Comprova que a base original não foi apagada nem alterada
            self.assertEqual(self.app.database.get_preference('workspace_name'), 'KIROS Espaço Matriz')
            self.assertTrue((self.data_dir / 'studio.sqlite3').exists())

    def test_restore_protects_existing_data_if_overwrite_false(self):
        """M12-A01: Restauração recusa sobrescrever diretório com dados se overwrite=False."""
        archive_path = self.backup_service.create_backup()

        with tempfile.TemporaryDirectory() as restore_tmp:
            target_dir = Path(restore_tmp)
            (target_dir / 'studio.sqlite3').write_text('existing data')

            with self.assertRaises(FileExistsError):
                self.backup_service.restore_backup(archive_path, target_dir, overwrite=False)

    def test_list_and_verify_backups(self):
        """M12-A01: Listagem e verificação em ambiente isolado."""
        b1 = self.backup_service.create_backup(name='b1.zip')
        backups = self.backup_service.list_backups()
        self.assertGreaterEqual(len(backups), 1)
        self.assertEqual(backups[0]['name'], 'b1.zip')

        # Verificação isolada temporária
        verification = self.backup_service.verify_backup(b1)
        self.assertEqual(verification['status'], 'success')
        self.assertEqual(verification['sqlite_integrity'], 'ok')


if __name__ == '__main__':
    unittest.main()
