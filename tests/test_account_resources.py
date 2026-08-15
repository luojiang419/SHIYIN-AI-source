import tempfile
import unittest
from pathlib import Path

from canvas_core.account_resources import AccountResourceService
from canvas_core.account_storage import AccountStorageRegistry
from canvas_core.accounts import AccountStore
from canvas_core.data_layout import DataLayout
from canvas_core.database import CanvasDatabase


class AccountResourceServiceTests(unittest.TestCase):
    def make_service(self, root: str):
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
        storage = AccountStorageRegistry(store, admin_layout, admin_database)
        return store, storage, AccountResourceService(store, storage)

    def test_lists_only_the_selected_accounts_files_and_database_records(self):
        with tempfile.TemporaryDirectory() as root:
            store, storage, service = self.make_service(root)
            first = store.register("001", "1")
            second = store.register("002", "2")
            first_layout = storage.layout_for(first.account_id)
            second_layout = storage.layout_for(second.account_id)
            (first_layout.media_generated / "first.png").write_bytes(b"first")
            (second_layout.media_generated / "second.png").write_bytes(b"second")
            storage.database_for(first.account_id).save_projects([{"id": "first", "name": "first project"}])
            storage.database_for(second.account_id).save_projects([{"id": "second", "name": "second project"}])

            payload = service.list_resources(first.account_id)
            self.assertEqual(payload["account"]["account"], "001")
            self.assertEqual([item["name"] for item in payload["files"]], ["first.png"])
            self.assertEqual([item["id"] for item in payload["projects"]], ["first"])
            self.assertNotIn("second.png", str(payload))

    def test_resolve_file_rejects_traversal_and_unknown_accounts(self):
        with tempfile.TemporaryDirectory() as root:
            store, storage, service = self.make_service(root)
            identity = store.register("9", "9")
            path = storage.layout_for(identity.account_id).exports / "safe.txt"
            path.write_text("safe", encoding="utf-8")
            self.assertEqual(service.resolve_file(identity.account_id, "exports", "safe.txt"), path.resolve())
            with self.assertRaises(PermissionError):
                service.resolve_file(identity.account_id, "exports", "../config/app.json")
            with self.assertRaises(KeyError):
                service.list_resources("missing")


if __name__ == "__main__":
    unittest.main()
