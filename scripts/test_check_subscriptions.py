import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_subscriptions as checks


class DirectoryCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "audits").mkdir()
        self.api = "https://catalog.example.test/api.php/provide/vod/"
        self.audit = {
            "directory": "https://directory.example.test/api/",
            "entries": [{
                "directory_id": "1",
                "directory_page": "https://directory.example.test/api/1.html",
                "status": "ADDED",
                "source_key": "sample",
                "group": "film-tv",
                "selected_api": self.api,
                "interfaces": [{"url": self.api}],
            }, {
                "directory_id": "2",
                "directory_page": "https://directory.example.test/api/2.html",
                "status": "WITHDRAWN_BY_DIRECTORY",
                "reason": "Directory withdrew the interface",
                "interfaces": [],
            }],
        }
        self.primary = {"sample": {"name": "Synthetic", "api": self.api}}

    def validate(self, audit):
        (self.root / "audits/sample.json").write_text(json.dumps(audit), encoding="utf-8")
        batch = {
            "audit": "audits/sample.json",
            "directory": audit["directory"],
            "content_sha256": checks.content_hash(audit),
            "entry_count": 2,
            "status_counts": {"ADDED": 1, "WITHDRAWN_BY_DIRECTORY": 1},
            "added_keys": ["sample"],
        }
        with patch.object(checks, "ROOT", self.root):
            checks.check_directory_imports({"directory_imports": [batch]}, self.primary, {"sample": "film-tv"})

    def test_complete_coverage_and_public_identity(self):
        self.validate(self.audit)

    def test_duplicate_directory_id_is_rejected(self):
        audit = copy.deepcopy(self.audit)
        audit["entries"][1]["directory_id"] = "1"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.validate(audit)

    def test_unpublished_selected_endpoint_is_rejected(self):
        audit = copy.deepcopy(self.audit)
        audit["entries"][0]["interfaces"] = [{"url": "https://another.example.test/vod"}]
        with self.assertRaisesRegex(ValueError, "not published"):
            self.validate(audit)

    def test_withdrawn_entry_cannot_invent_source_identity(self):
        audit = copy.deepcopy(self.audit)
        audit["entries"][1]["source_key"] = "sample"
        with self.assertRaisesRegex(ValueError, "Rejected"):
            self.validate(audit)

    def test_localhost_private_addresses_and_credentials_are_rejected(self):
        addresses = [
            "http://localhost/vod",
            "http://LOCALHOST./vod",
            "http://a.localhost/vod",
            "https://127.0.0.1/vod",
            "http://10.0.0.1/vod",
            "http://[::1]/vod",
            "https://user:secret@public.example.test/vod",
        ]
        for api in addresses:
            with self.subTest(api=api), self.assertRaises(ValueError):
                checks.source_identity({"api": api})

    def test_semantic_query_and_encoded_path_remain_distinct(self):
        base = {"api": "https://catalog.example.test/vod%2Fdetail?ac=list"}
        self.assertNotEqual(
            checks.source_identity(base),
            checks.source_identity({"api": "https://catalog.example.test/vod/detail"}),
        )
        self.assertNotEqual(
            checks.source_identity(base),
            checks.source_identity({"api": "https://catalog.example.test/vod%2Fdetail?from=other"}),
        )


if __name__ == "__main__":
    unittest.main()
