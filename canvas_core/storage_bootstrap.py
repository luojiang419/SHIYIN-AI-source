from .data_layout import DataLayout
from .database import CanvasDatabase
from .accounts import AccountStore
from .account_storage import AccountStorageRegistry, ScopedDataLayoutProxy, ScopedDatabaseProxy
from .migration import LegacyMigrator
from .maintenance import MaintenanceManager
from .paths import APP_PATHS
from .secrets import SecretStore
from .dwpose_models import DWPoseModelManager
from .depth_models import DepthModelManager
from .person_depth_components import PersonDepthComponentManager


ADMIN_DATA_LAYOUT = DataLayout.from_app_paths(APP_PATHS)
ADMIN_DATA_LAYOUT.ensure()

MAINTENANCE = MaintenanceManager(ADMIN_DATA_LAYOUT)
MAINTENANCE_REPORT = MAINTENANCE.latest_report()
MAINTENANCE.start()

ADMIN_DATABASE = CanvasDatabase(ADMIN_DATA_LAYOUT.database_file)
ADMIN_DATABASE.initialize()

MIGRATION_REPORT = LegacyMigrator(APP_PATHS, ADMIN_DATA_LAYOUT, ADMIN_DATABASE).run()

SECRET_STORE = SecretStore(ADMIN_DATABASE)
_legacy_secret_files = sorted(ADMIN_DATA_LAYOUT.backups.glob("migration-*/legacy-root/API/.env"))
_legacy_secret_files.append(ADMIN_DATA_LAYOUT.secret_env)
SECRET_MIGRATION_REPORT = SECRET_STORE.import_env_files(_legacy_secret_files)
SECRET_STORE.load_into_environ()

ACCOUNT_STORE = AccountStore(APP_PATHS.data_root)
ACCOUNT_STORE.initialize()
DWPOSE_MODEL_MANAGER = DWPoseModelManager(ACCOUNT_STORE.system_root / "models" / "dwpose")
DEPTH_MODEL_MANAGER = DepthModelManager(ACCOUNT_STORE.system_root / "models" / "depth")
PERSON_DEPTH_COMPONENT_MANAGER = PersonDepthComponentManager(
    ACCOUNT_STORE.system_root / "components" / "person-depth"
)
ACCOUNT_STORAGE = AccountStorageRegistry(ACCOUNT_STORE, ADMIN_DATA_LAYOUT, ADMIN_DATABASE)
DATA_LAYOUT = ScopedDataLayoutProxy(ACCOUNT_STORAGE)
DATABASE = ScopedDatabaseProxy(ACCOUNT_STORAGE)
