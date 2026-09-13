import sqlite3
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
from kiros.learning import LearningService, PromptLibrary
from kiros.search import GlobalSearchService
from kiros.command_bar import CommandBarService
from kiros.dashboard import DashboardService
from kiros.backup import BackupService

NAVIGATION = (
    ('inicio', 'Início'),
    ('biblioteca', 'Produtos & Biblioteca'),
    ('criar', 'Ideias & Criar'),
    ('conteudo', 'Conteúdo & Aprovação'),
    ('calendario', 'Calendário & Fila'),
    ('insights', 'Insights'),
    ('marca', 'Marca'),
    ('configuracoes', 'Configurações'),
)


class Application:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.database = SQLiteDatabase(data_dir / 'studio.sqlite3')
        self._init_policy()
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
        self.learning = LearningService(self.database, self.library, self.memory)
        self.prompt_library = PromptLibrary(self.database)
        self.search = GlobalSearchService(self.database)
        self.command_bar = CommandBarService(
            database=self.database,
            campaigns=self.campaigns,
            cost_manager=self.cost_manager,
            queue=self.queue,
            idea_bank=self.idea_bank,
            search_service=self.search,
        )
        self.dashboard = DashboardService(
            database=self.database,
            library=self.library,
            campaigns=self.campaigns,
            queue=self.queue,
            calendar=self.calendar,
            idea_bank=self.idea_bank,
            learning=self.learning,
            prompt_library=self.prompt_library,
        )
        self.backup = BackupService(self.data_dir, self.database, self.storage)

    def _init_policy(self):
        env_policy = Policy.from_env()
        mode = env_policy.mode
        allow_paid = env_policy.allow_paid
        allow_publish = env_policy.allow_publish

        try:
            with sqlite3.connect(self.database.path) as conn:
                r_mode = conn.execute("SELECT value FROM preferences WHERE key='provider_mode'").fetchone()
                if r_mode and r_mode[0]:
                    mode = r_mode[0]
                r_paid = conn.execute("SELECT value FROM preferences WHERE key='allow_paid_apis'").fetchone()
                if r_paid and r_paid[0] is not None:
                    allow_paid = (r_paid[0] == '1')
                r_pub = conn.execute("SELECT value FROM preferences WHERE key='allow_publish'").fetchone()
                if r_pub and r_pub[0] is not None:
                    allow_publish = (r_pub[0] == '1')
        except Exception:
            pass

        self.policy = Policy(mode=mode, allow_paid=allow_paid, allow_publish=allow_publish)
        self.gateway = ExternalGateway(self.policy)

    def get_gateway_policy(self) -> dict:
        return {
            'mode': self.gateway.policy.mode,
            'allow_paid': self.gateway.policy.allow_paid,
            'allow_publish': self.gateway.policy.allow_publish,
        }

    def update_gateway_policy(self, mode: str, allow_paid: bool = False, allow_publish: bool = False) -> None:
        if mode not in ('mock', 'live'):
            raise ValueError("Modo de operação inválido. Escolha 'mock' ou 'live'.")
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.database.path) as conn:
            conn.execute(
                "INSERT INTO preferences (key, value, source, reference, recorded_at) VALUES ('provider_mode', ?, 'user', 'settings', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, recorded_at=excluded.recorded_at",
                (mode, now)
            )
            conn.execute(
                "INSERT INTO preferences (key, value, source, reference, recorded_at) VALUES ('allow_paid_apis', ?, 'user', 'settings', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, recorded_at=excluded.recorded_at",
                ('1' if allow_paid else '0', now)
            )
            conn.execute(
                "INSERT INTO preferences (key, value, source, reference, recorded_at) VALUES ('allow_publish', ?, 'user', 'settings', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, recorded_at=excluded.recorded_at",
                ('1' if allow_publish else '0', now)
            )
            conn.commit()
        self.gateway.set_policy(mode=mode, allow_paid=allow_paid, allow_publish=allow_publish)
        self.policy = self.gateway.policy
        if hasattr(self, 'publisher') and self.publisher:
            self.publisher.mock_mode = (mode == 'mock')

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
