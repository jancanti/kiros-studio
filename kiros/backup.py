"""Serviço de Backup e Restauração Consistente do KIROS Studio (Seção 71 e M12-A01).

Escopo do Backup:
- SQLite (snapshot atômico e consistente via sqlite3.backup);
- Brand Bible (versões da marca e overrides);
- Product Bible (produtos, versões da ficha visual, referências visuais);
- Campanhas (storyboards, pipelines, aprovações, execuções e versões);
- Assets (todos os arquivos de fotos e imagens armazenados no filesystem local);
- Configurações importantes (preferências do workspace, calendários, custos e provedores).

Princípios:
- Backup atômico sem corrupção ou tabelas bloqueadas;
- Nunca apaga histórico automaticamente durante ou após o backup;
- Restauração validada com integridade estrutural sem apagar o banco original.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any, Dict, List, Optional
import zipfile

from kiros.core.contracts import Provenance
from kiros.infrastructure.local import FileStorage, SQLiteDatabase


class BackupService:
    """Gerencia backups consistentes de banco SQLite, arquivos e metadados com restauração segura."""

    def __init__(self, data_dir: Path, database: SQLiteDatabase, storage: FileStorage):
        self.data_dir = Path(data_dir)
        self.database = database
        self.storage = storage
        self.backups_dir = self.data_dir / 'backups'
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_backup(self, dest_dir: Optional[Path] = None, name: Optional[str] = None) -> Path:
        """Gera backup consistente empacotado em arquivo ZIP contendo SQLite, assets e manifesto.
        
        Não remove nenhum histórico ou backup anterior.
        """
        output_dir = Path(dest_dir) if dest_dir else self.backups_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        now_str = self._now()
        timestamp_slug = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        archive_name = name or f"kiros_backup_{timestamp_slug}.zip"
        if not archive_name.endswith('.zip'):
            archive_name += '.zip'
        archive_path = output_dir / archive_name

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            temp_db_path = temp_path / 'studio.sqlite3'

            # 1. Snapshot atômico e consistente do SQLite via Online Backup API
            with sqlite3.connect(self.database.path) as src_conn:
                with sqlite3.connect(temp_db_path) as dest_conn:
                    src_conn.backup(dest_conn)

            # 2. Hash SHA-256 do SQLite para integridade
            hasher = hashlib.sha256()
            with open(temp_db_path, 'rb') as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            sqlite_sha256 = hasher.hexdigest()

            # 3. Estatísticas dos dados protegidos
            stats = self._collect_stats(temp_db_path)

            # 4. Criação do manifesto estruturado
            files_root = self.data_dir / 'files'
            files_to_pack: List[Path] = []
            if files_root.exists():
                for p in files_root.rglob('*'):
                    if p.is_file() and not p.name.startswith('.'):
                        files_to_pack.append(p)

            manifest = {
                'version': '1.0.0',
                'created_at': now_str,
                'archive_name': archive_name,
                'sqlite_sha256': sqlite_sha256,
                'stats': stats,
                'files_count': len(files_to_pack),
                'provenance': {
                    'source': 'automatic_analysis',
                    'reference': 'backup_service',
                    'recorded_at': now_str,
                },
                'policy': {
                    'auto_delete_history': False,
                    'atomic_snapshot': True,
                },
            }

            manifest_path = temp_path / 'manifest.json'
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')

            # 5. Empacotamento em ZIP com compressão DEFLATED
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(temp_db_path, arcname='studio.sqlite3')
                zf.write(manifest_path, arcname='manifest.json')
                for fpath in files_to_pack:
                    rel = fpath.relative_to(files_root)
                    zf.write(fpath, arcname=f"files/{rel}")

        return archive_path

    def restore_backup(
        self,
        archive_path: Path,
        target_dir: Path,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Restaura o backup para um diretório alvo.
        
        Se overwrite=False e o diretório já contiver studio.sqlite3, recusa a operação
        para proteger e nunca apagar os dados originais.
        """
        archive = Path(archive_path)
        if not archive.exists():
            raise FileNotFoundError(f"Arquivo de backup não encontrado: {archive}")

        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)
        target_sqlite = target / 'studio.sqlite3'

        if target_sqlite.exists() and not overwrite:
            raise FileExistsError(
                f"O diretório alvo '{target}' já contém banco de dados. "
                "Para preservar o original e evitar perda de dados, a restauração foi cancelada (overwrite=False)."
            )

        with zipfile.ZipFile(archive, 'r') as zf:
            namelist = zf.namelist()
            if 'studio.sqlite3' not in namelist:
                raise ValueError("Backup corrompido ou inválido: arquivo 'studio.sqlite3' ausente.")
            if 'manifest.json' not in namelist:
                raise ValueError("Backup inválido: arquivo 'manifest.json' ausente.")

            # Extração
            zf.extractall(target)

        # Validação de integridade do banco restaurado
        hasher = hashlib.sha256()
        with open(target_sqlite, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        restored_sha = hasher.hexdigest()

        manifest_content = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
        expected_sha = manifest_content.get('sqlite_sha256')
        if expected_sha and restored_sha != expected_sha:
            raise ValueError(f"Divergência de hash SHA-256 no SQLite restaurado (esperado {expected_sha}, obtido {restored_sha})")

        with sqlite3.connect(target_sqlite) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != 'ok':
                raise ValueError(f"Falha no PRAGMA integrity_check do SQLite restaurado: {integrity}")
            tables_row = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()
            table_count = tables_row[0] if tables_row else 0

        restored_files_count = 0
        target_files = target / 'files'
        if target_files.exists():
            restored_files_count = sum(1 for p in target_files.rglob('*') if p.is_file())

        return {
            'status': 'success',
            'restored_to': str(target),
            'sqlite_integrity': 'ok',
            'tables_count': table_count,
            'restored_files_count': restored_files_count,
            'manifest': manifest_content,
            'restored_at': self._now(),
        }

    def verify_backup(self, archive_path: Path) -> Dict[str, Any]:
        """Inspeciona e valida o arquivo de backup em ambiente isolado temporário."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            return self.restore_backup(archive_path, Path(tmp_dir), overwrite=True)

    def list_backups(self) -> List[Dict[str, Any]]:
        """Lista os backups disponíveis ordenados pelo mais recente."""
        if not self.backups_dir.exists():
            return []

        backups = []
        for p in self.backups_dir.glob('*.zip'):
            try:
                stat = p.stat()
                manifest = {}
                with zipfile.ZipFile(p, 'r') as zf:
                    if 'manifest.json' in zf.namelist():
                        manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
                backups.append({
                    'name': p.name,
                    'path': str(p),
                    'size_bytes': stat.st_size,
                    'modified_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    'created_at': manifest.get('created_at', ''),
                    'files_count': manifest.get('files_count', 0),
                    'stats': manifest.get('stats', {}),
                })
            except Exception:
                pass

        backups.sort(key=lambda b: b['created_at'] or b['modified_at'], reverse=True)
        return backups

    def _collect_stats(self, sqlite_path: Path) -> Dict[str, int]:
        """Coleta contagens de registros das principais entidades para o manifesto."""
        stats: Dict[str, int] = {}
        with sqlite3.connect(sqlite_path) as conn:
            conn.row_factory = sqlite3.Row
            tables = [
                ('campaigns', 'campaigns'),
                ('storyboard_slides', 'slides'),
                ('products', 'products'),
                ('visual_references', 'visual_references'),
                ('bible_versions', 'bible_versions'),
                ('execution_versions', 'execution_versions'),
                ('ideas', 'ideas'),
                ('layout_templates', 'layout_templates'),
                ('calendar_entries', 'calendar_entries'),
                ('social_publications', 'social_publications'),
                ('cost_records', 'cost_records'),
                ('learning_proposals', 'learning_proposals'),
                ('prompt_library', 'prompt_library'),
            ]
            for tbl, key in tables:
                try:
                    row = conn.execute(f"SELECT count(*) FROM {tbl}").fetchone()
                    stats[key] = int(row[0]) if row else 0
                except Exception:
                    stats[key] = 0
        return stats
