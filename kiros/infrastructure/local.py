import os
import sqlite3
import tempfile
from pathlib import Path
from kiros.core.contracts import Provenance


class SQLiteDatabase:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = path
        self.migrate()
        os.chmod(path, 0o600)

    def migrate(self):
        migrations = Path(__file__).resolve().parents[1] / 'migrations'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)')
            for file in sorted(migrations.glob('*.sql')):
                if not db.execute('SELECT 1 FROM schema_migrations WHERE version=?', (file.name,)).fetchone():
                    # Migration and version are committed together, or rolled back.
                    db.execute('BEGIN')
                    for statement in file.read_text().split(';'):
                        if statement.strip():
                            db.execute(statement)
                    db.execute('INSERT INTO schema_migrations VALUES (?)', (file.name,))
                    db.commit()

    def set_preference(self, key: str, value: str, provenance: Provenance):
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO preferences VALUES (?, ?, ?, ?, ?) '
                       'ON CONFLICT(key) DO UPDATE SET value=excluded.value, '
                       'source=excluded.source, reference=excluded.reference, recorded_at=excluded.recorded_at',
                       (key, value, provenance.source, provenance.reference, provenance.recorded_at))

    def get_preference(self, key: str) -> str:
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT value FROM preferences WHERE key=?', (key,)).fetchone()
        return row[0] if row else ''


class FileStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, key: str) -> Path:
        relative = Path(key)
        if not key or relative.is_absolute() or '..' in relative.parts or '\\' in key or '\x00' in key or key == '.':
            raise ValueError('Caminho inválido')
        path = self.root / relative
        if any(parent.is_symlink() for parent in [path, *path.parents] if parent != self.root and self.root in parent.parents):
            raise ValueError('Links simbólicos não permitidos')
        if self.root not in path.resolve().parents:
            raise ValueError('Caminho fora do armazenamento')
        return path

    def put(self, key: str, content: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()
