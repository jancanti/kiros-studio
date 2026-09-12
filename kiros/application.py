from datetime import datetime, timezone
from pathlib import Path
from kiros.core.contracts import Provenance
from kiros.core.director import CreativeDirector
from kiros.infrastructure.local import SQLiteDatabase, FileStorage
from kiros.infrastructure.security import Policy, ExternalGateway
from kiros.providers.mock import MockLLM, MockVision
from kiros.library import Library
from kiros.providers.manager import ProviderManager
from kiros.providers.router import ImageEngineRouter
from kiros.cost import CostManager
from kiros.context import ContextOptimizer
from kiros.director.memory import MemoryStore
from kiros.director.ideas import IdeaBank
from kiros.campaigns.manager import CampaignManager
from kiros.execution.queue import ExecutionQueue
from kiros.execution.worker import ExecutionWorker

NAVIGATION = (
    ('inicio', 'Início'), ('criar', 'Criar'), ('calendario', 'Calendário'),
    ('conteudo', 'Conteúdo'), ('biblioteca', 'Biblioteca'), ('insights', 'Insights'),
    ('marca', 'Marca'), ('configuracoes', 'Configurações'),
)


class Application:
    def __init__(self, data_dir: Path):
        self.policy = Policy.from_env()
        self.gateway = ExternalGateway(self.policy)
        self.database = SQLiteDatabase(data_dir / 'studio.sqlite3')
        self.storage = FileStorage(data_dir / 'files')
        self.library = Library(self.database, self.storage, MockVision())
        self.memory = MemoryStore(self.database)
        self.idea_bank = IdeaBank(self.database)
        self.director = CreativeDirector(MockLLM(), self.library, self.memory, self.idea_bank)
        self.providers = ProviderManager(self.database, self.gateway)
        self.router = ImageEngineRouter(self.database, self.providers)
        self.cost_manager = CostManager(self.database)
        self.context_optimizer = ContextOptimizer(self.cost_manager)
        self.queue = ExecutionQueue(self.database, self.cost_manager)
        self.worker = ExecutionWorker(self.queue, self.providers, self.storage)
        self.campaigns = CampaignManager(self.database, self.cost_manager, self.router, self.queue)

    def status(self):
        # Lista explícita: nunca serializar ambiente, configurações ou segredos.
        active_count = len(self.providers.list_providers(active_only=True))
        return {
            'status': 'ok',
            'provider': 'mock',
            'external_calls': 'unavailable' if self.policy.mode == 'mock' else 'live',
            'active_providers_count': active_count,
            'workspace_name': self.database.get_preference('workspace_name') or 'KIROS Aromas',
        }

    def rename_workspace(self, value):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80:
            raise ValueError('Use um nome entre 1 e 80 caracteres.')
        self.database.set_preference('workspace_name', value.strip(), Provenance(
            'user', 'settings.workspace_name', datetime.now(timezone.utc).isoformat()))
