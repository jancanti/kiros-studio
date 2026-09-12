"""Build local sem rede: valida sintaxe e empacota fontes e recursos."""
import ast
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
files = sorted(p for p in (root / 'kiros').rglob('*') if p.suffix in {'.py', '.sql', '.css'})
for file in files:
    if file.suffix == '.py':
        ast.parse(file.read_text(), filename=str(file))
(root / 'dist').mkdir(exist_ok=True)
with ZipFile(root / 'dist/kiros-studio.zip', 'w', ZIP_DEFLATED) as archive:
    for file in files:
        archive.write(file, file.relative_to(root))
print(f'Build local: {len(files)} arquivos em dist/kiros-studio.zip')
