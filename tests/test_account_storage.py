import tempfile
import unittest
from pathlib import Path

from canvas_core.account_storage import (
    AccountStorageRegistry,
    ScopedDataLayoutProxy,
    ScopedDatabaseProxy,
    account_scope,
    current_account_id,
)
from canvas_core.accounts import AccountStore
from canvas_core.data_layout import DataLayout
from canvas_core.database import CanvasDatabase


class AccountStorageTests(unittest.TestCase):
    def make_registry(self, root: str):
        base = Path(root)
        admin_layout = DataLayout.from_root(base)
        admin_layout.ensure()
        admin_database = CanvasDatabase(admin_layout.database_file)
        admin_database.initialize()
        store = AccountStore(
            base,
            protect=lambda value: value.encode("utf-8"),
            unprotect=lambda value: bytes(value).decode("utf-8"),
        )
        store.initialize()
        registry = AccountStorageRegistry(store, admin_layout, admin_database)
        return store, registry

    def test_database_and_layout_follow_account_context(self):
        with tempfile.TemporaryDirectory() as root:
            store, registry = self.make_registry(root)
            first = store.register("1", "1")
            second = store.register("2", "2")
            database = ScopedDatabaseProxy(registry)
            layout = ScopedDataLayoutProxy(registry)

            database.save_projects([{"id": "admin-project", "name": "管理员"}])
            with account_scope(first.account_id):
                self.assertEqual(current_account_id(), first.account_id)
                database.save_projects([{"id": "first-project", "name": "用户一"}])
                self.assertIn(first.folder_name, str(layout.root))
                self.assertEqual([item["id"] for item in database.load_projects()], ["first-project"])
            with account_scope(second.account_id):
                self.assertEqual(database.load_projects(), [])
                database.save_projects([{"id": "second-project", "name": "用户二"}])
            with account_scope(first.account_id):
                self.assertEqual([item["id"] for item in database.load_projects()], ["first-project"])
            self.assertEqual([item["id"] for item in database.load_projects()], ["admin-project"])

    def test_context_is_restored_after_nested_scope(self):
        with tempfile.TemporaryDirectory() as root:
            store, registry = self.make_registry(root)
            identity = store.register("3", "3")
            self.assertEqual(current_account_id(), "admin")
            with account_scope(identity.account_id):
                self.assertEqual(current_account_id(), identity.account_id)
                with account_scope("admin"):
                    self.assertEqual(current_account_id(), "admin")
                self.assertEqual(current_account_id(), identity.account_id)
            self.assertEqual(current_account_id(), "admin")


if __name__ == "__main__":
    unittest.main()
