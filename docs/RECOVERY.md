# Instruções de Operação, Backup e Recuperação da V1

Este guia documenta as operações essenciais de inicialização, realização de backups consistentes e procedimentos de recuperação de dados do **KIROS Studio V1**, cumprindo o critério **M12-A05** e a **Seção 71** da especificação.

---

## 1. Arquitetura de Dados Local

O KIROS Studio V1 opera integralmente em ambiente local e determinístico:

- **Banco de Dados Relacional**: Arquivo SQLite em `data/kiros.db` com integridade referencial (`PRAGMA foreign_keys = ON`), transações atômicas e migrações versionadas (001 a 012).
- **Armazenamento de Arquivos**: Diretório `data/storage/` contendo arquivos estáticos, fotos originais de produtos, referências visuais de campanha e assets gerados.
- **Configurações e Segredos**: Criptografados e mascarados; segredos nunca vazam em logs ou respostas HTTP.
- **Histórico**: Princípio de governança da Seção 71: **nunca apagar histórico automaticamente**.

---

## 2. Procedimento de Backup (Seção 71)

O `BackupService` (`kiros/backup.py`) gera pacotes compactados em formato `.zip` com garantia de consistência atômica:

1. **Backup Atômico do SQLite**: Utiliza o comando `sqlite3.backup()` na conexão ativa, garantindo consistência sem corrupção mesmo com leituras simultâneas.
2. **Cópia de Arquivos e Assets**: Inclui Brand Bible, Product Bible, imagens de produto, referências e assets de campanha.
3. **Manifesto Criptográfico (`manifest.json`)**:
   - Hash SHA-256 de cada arquivo incluído no backup.
   - Contagem de registros por entidade (campanhas, produtos, versões de execução, regras de marca, memórias).
   - Timestamp UTC e metadados de versão da aplicação.
4. **Preservação de Histórico**: Registra explicitamente `auto_delete_history: false`.

### Formas de Realização do Backup:

- **Pela Interface Web**:
  Acesse `/configuracoes` -> painel **Backup e Restauração (Seção 71)** -> clique no botão **"Gerar Backup Completo Agora"**.
- **Pela API HTTP**:
  ```bash
  curl -X POST http://127.0.0.1:8765/api/backup/create -d "note=Backup_Rotina"
  ```
- **Por Script Python**:
  ```python
  from kiros.backup import BackupService
  from kiros.infrastructure.local import SQLiteDatabase, FileStorage

  db = SQLiteDatabase("data/kiros.db")
  storage = FileStorage("data/storage")
  service = BackupService(data_dir="data", database=db, storage=storage)
  backup_file = service.create_backup(note="Rotina Operacional")
  print("Backup gerado em:", backup_file)
  ```

---

## 3. Procedimento de Restauração Segura (M12-A01)

Por segurança operacional, a restauração **nunca apaga nem sobrescreve a base ativa diretamente**. Ela é sempre extraída em um diretório de destino isolado, permitindo inspeção e auditoria antes da substituição definitiva:

```python
from kiros.backup import BackupService
from kiros.infrastructure.local import SQLiteDatabase, FileStorage

db = SQLiteDatabase("data/kiros.db")
storage = FileStorage("data/storage")
service = BackupService(data_dir="data", database=db, storage=storage)

# 1. Verifica integridade do arquivo de backup
verification = service.verify_backup("data/backups/kiros_backup_20260912_170000.zip")
assert verification["valid"] is True

# 2. Restaura em diretório isolado (sem apagar o original)
manifest = service.restore_backup(
    backup_zip_path="data/backups/kiros_backup_20260912_170000.zip",
    destination_dir="data_restored"
)
print("Restauração concluída com sucesso:", manifest["entities"])
```

### Validação Pós-Restauração:
Após restaurar para o diretório de contingência, inicie uma instância secundária para conferir a integridade:
```bash
python3 -m kiros --data-dir data_restored --port 8766
```

---

## 4. Inicialização do Servidor e Diagnóstico

### Inicialização em Produção / Desenvolvimento Local:
```bash
python3 -m kiros --port 8765
```

### Validação de Saúde (Smoke Test):
Executa requisições de teste nas rotas principais, testa persistência após reinício e valida integridade do SQLite:
```bash
python3 scripts/smoke.py
```

### Execução da Suíte Completa de Testes:
```bash
python3 -m unittest discover -s tests -v
```

### Empacotamento para Distribuição:
```bash
python3 scripts/build.py
```
Gera o pacote `dist/kiros-studio.zip` contendo os 76 arquivos da aplicação.

