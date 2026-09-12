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

from kiros.fidelity import ProductFidelityService
from kiros.layout import LayoutEngine, LayoutEditor, TemplateLibrary
from kiros.content import CopyEngine, StoriesEngine, PrePublishAuditor
from kiros.calendar import EditorialCalendarService
from kiros.social import InstagramPublisher, PublicationAuditor
from kiros.insights import InsightsService

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
        self.fidelity_service = ProductFidelityService(
            self.database, self.library, self.cost_manager, self.storage, self.memory
        )
        self.queue = ExecutionQueue(
            self.database, self.cost_manager, fidelity_service=self.fidelity_service, memory_store=self.memory
        )
        self.worker = ExecutionWorker(self.queue, self.providers, self.storage)
        self.layout_engine = LayoutEngine()
        self.template_library = TemplateLibrary(self.database)
        self.layout_editor = LayoutEditor(self.database, self.layout_engine, self.library)
        self.copy_engine = CopyEngine()
        self.stories_engine = StoriesEngine()
        self.pre_publish_auditor = PrePublishAuditor(self.copy_engine, self.stories_engine)
        self.campaigns = CampaignManager(
            self.database,
            self.cost_manager,
            self.router,
            self.queue,
            fidelity_service=self.fidelity_service,
            layout_editor=self.layout_editor,
            template_library=self.template_library,
            copy_engine=self.copy_engine,
            stories_engine=self.stories_engine,
            pre_publish_auditor=self.pre_publish_auditor,
            library=self.library,
        )
        self.publication_auditor = PublicationAuditor(
            campaigns=self.campaigns,
            library=self.library,
            pre_publish_auditor=self.pre_publish_auditor,
            fidelity_service=self.fidelity_service,
        )
        self.publisher = InstagramPublisher(
            database=self.database,
            gateway=self.gateway,
            auditor=self.publication_auditor,
            mock_mode=(self.policy.mode == 'mock'),
        )
        self.calendar = EditorialCalendarService(
            database=self.database,
            campaigns=self.campaigns,
            library=self.library,
        )
        self.insights = InsightsService(self.database)

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
