import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_subscriptions as checks


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "subscriptions").mkdir()
        self.groups = {group: (name, 1) for group, (name, _) in checks.GROUPS.items()}
        self.documents = {
            group: {"cache_time": 7200, "api_site": {
                group: {"name": name, "api": f"https://{group}.example.test/vod"}
            }}
            for group, (name, _) in self.groups.items()
        }

    def validate(self):
        for group, document in self.documents.items():
            (self.root / "subscriptions" / f"{group}.json").write_text(json.dumps(document), encoding="utf-8")
        with patch.object(checks, "GROUPS", self.groups):
            return checks.check(self.root)

    def sample(self):
        return self.documents["film-tv"]["api_site"]["film-tv"]

    def test_four_current_subscriptions_pass(self):
        self.assertEqual(self.validate()["sources"], 4)

    def test_missing_group_is_rejected(self):
        self.validate()
        (self.root / "subscriptions/unknown.json").unlink()
        with patch.object(checks, "GROUPS", self.groups), self.assertRaisesRegex(ValueError, "missing"):
            checks.check(self.root)

    def test_extra_json_anywhere_is_rejected(self):
        for relative in ("config.json", "subscriptions/index.json", "archive/old.json", "audits/old.JSON"):
            with self.subTest(relative=relative):
                path = self.root / relative
                path.parent.mkdir(exist_ok=True)
                path.write_text("{}", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "extra"):
                    self.validate()
                path.unlink()

    def test_inventory_count_change_is_rejected(self):
        self.documents["film-tv"]["api_site"]["additional"] = {"name": "Extra", "api": "https://other.example.test/vod"}
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            self.validate()

    def test_duplicate_stable_key_is_rejected(self):
        self.documents["unknown"]["api_site"] = {"film-tv": {"name": "Other", "api": "https://different.example.test/vod"}}
        with self.assertRaisesRegex(ValueError, "Duplicate source"):
            self.validate()

    def test_equivalent_api_identity_is_rejected(self):
        self.documents["unknown"]["api_site"]["unknown"]["api"] = "https://FILM-TV.example.test:443/vod/?ac=list"
        with self.assertRaisesRegex(ValueError, "Duplicate source"):
            self.validate()

    def test_protocol_query_detail_and_encoded_path_remain_distinct(self):
        base = {"name": "Synthetic", "api": "https://catalog.example.test/vod%2Fdetail?ac=list"}
        for changes in (
            {"api": "http://catalog.example.test/vod%2Fdetail?ac=list"},
            {"api": "https://catalog.example.test/vod/detail?ac=list"},
            {"api": "https://catalog.example.test/vod%2Fdetail?from=other"},
            {"detail": "https://detail.example.test/vod"},
        ):
            with self.subTest(changes=changes):
                self.assertNotEqual(checks.source_identity(base), checks.source_identity(base | changes))

    def test_duplicate_json_keys_are_rejected(self):
        self.validate()
        (self.root / "subscriptions/film-tv.json").write_text('{"cache_time":7200,"cache_time":7200,"api_site":{}}', encoding="utf-8")
        with patch.object(checks, "GROUPS", self.groups), self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            checks.check(self.root)

    def test_envelope_requires_exact_keys_and_types(self):
        for value in ([], {"cache_time": True, "api_site": {}}, {"cache_time": 7200, "api_site": []},
                      {"cache_time": 7200, "api_site": {}, "index": {}}):
            with self.subTest(value=value):
                previous = self.documents["film-tv"]
                self.documents["film-tv"] = value
                with self.assertRaisesRegex(ValueError, "envelope"):
                    self.validate()
                self.documents["film-tv"] = previous

    def test_invalid_source_schema_is_rejected(self):
        for value in ([], {"api": "https://catalog.example.test/vod"},
                      {"name": "Synthetic", "api": "https://catalog.example.test/vod", "script": "x"}):
            with self.subTest(value=value):
                self.documents["film-tv"]["api_site"]["film-tv"] = value
                with self.assertRaises(ValueError):
                    self.validate()

    def test_invalid_public_api_and_detail_endpoints_are_rejected(self):
        addresses = [
            "http://localhost/vod", "http://LOCALHOST./vod", "http://a.localhost/vod",
            "https://127.0.0.1/vod", "http://10.0.0.1/vod", "http://[::1]/vod",
            "https://user:secret@public.example.test/vod", "ftp://catalog.example.test/vod",
            "https://catalog.example.test/vod#fragment", "https://catalog.example.test:/vod",
            "https://catalog.example.test:0/vod", "https://catalog.example.test:65536/vod",
            "https://catalog.example.test/has space", "https://catalog.example.test/vod\\other",
        ]
        for field in ("api", "detail"):
            for address in addresses:
                with self.subTest(field=field, address=address):
                    site = {"name": "Synthetic", "api": "https://catalog.example.test/vod", field: address}
                    with self.assertRaises(ValueError):
                        checks.source_identity(site)

    def test_disabled_and_nonboolean_flags_are_rejected(self):
        for disabled in (True, "false", 0, None):
            with self.subTest(disabled=disabled):
                self.sample()["disabled"] = disabled
                with self.assertRaises(ValueError):
                    self.validate()

    def test_native_adapter_requires_supported_identity_and_version(self):
        site = {"name": "Synthetic", "api": "https://catalog.example.test", "adapter": "tencent", "native": {"version": 1}}
        self.assertEqual(checks.source_identity(site), ("native", "tencent"))
        for changes in ({"adapter": "unsupported"}, {"adapter": []}, {"native": None},
                        {"native": {}}, {"native": {"version": True}}, {"native": {"version": 2}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                checks.source_identity(site | changes)

    def test_builtin_jianpian_without_native_override_is_valid(self):
        site = {"name": "Synthetic", "api": "https://catalog.example.test", "adapter": "jianpian"}
        self.assertEqual(checks.source_identity(site), ("native", "jianpian"))

    def test_native_configuration_without_adapter_is_rejected(self):
        self.sample()["native"] = {"version": 1}
        with self.assertRaisesRegex(ValueError, "requires an adapter"):
            self.validate()

    def test_same_native_adapter_in_two_groups_is_rejected(self):
        for group in ("film-tv", "unknown"):
            self.documents[group]["api_site"][group].update(adapter="tencent", native={"version": 1})
        with self.assertRaisesRegex(ValueError, "Duplicate source"):
            self.validate()

    def test_explicit_adult_marker_stays_in_unknown(self):
        self.sample()["name"] = "Synthetic 🔞"
        with self.assertRaisesRegex(ValueError, "unknown group"):
            self.validate()

    def test_name_cleanup_preserves_words_numbers_and_adult_markers(self):
        examples = {
            "🎬爱奇艺": "爱奇艺",
            "影视 • 索尼[直连]": "影视 索尼 直连",
            "鸭鸭（丫丫）资源网": "鸭鸭 丫丫 资源网",
            "🔞91精品": "成人 91精品",
            "66-360*": "66 360",
            "Clun📚在线·茅台 | 采集": "Clun 在线 茅台 采集",
            "1080资源库(切)": "1080资源库 切",
            "影视2": "影视2",
            "1717云资源网采集api": "1717云资源网采集api",
            "90s影视": "90s影视",
            "iKun资源": "iKun资源",
        }
        for original, expected in examples.items():
            with self.subTest(original=original):
                self.assertEqual(checks.clean_source_name(original), expected)

    def test_latency_blocks_and_standalone_milliseconds_are_removed(self):
        for name in ("[590ms|5] 影视2", "【37 ms|直播】影视2",
                     "（延迟32毫秒）影视2", "影视2 延迟：1.5ms", "影视2  18 毫秒"):
            with self.subTest(name=name):
                self.assertEqual(checks.clean_source_name(name), "影视2")

    def test_decorated_latency_and_untrimmed_names_are_rejected(self):
        for name in ("🎬影视2", "影视┃直连", "影视(直连)", "影视2  资源",
                     " 影视2", "影视2\u200b", "[590ms|5] 影视2", "影视2 32毫秒"):
            with self.subTest(name=name):
                self.sample()["name"] = name
                with self.assertRaisesRegex(ValueError, "Source name"):
                    self.validate()

    def test_plain_adult_marker_must_stay_in_unknown(self):
        self.sample()["name"] = "成人 Synthetic"
        with self.assertRaisesRegex(ValueError, "unknown group"):
            self.validate()

    def test_duplicate_display_names_are_reported_without_merging(self):
        for document in self.documents.values():
            next(iter(document["api_site"].values()))["name"] = "Same source"
        result = self.validate()
        self.assertEqual(result["sources"], 4)
        self.assertEqual(len(result["duplicate_names"]["Same source"]), 4)

    def test_current_repository_inventory_passes(self):
        self.assertEqual(checks.check()["sources"], 207)


if __name__ == "__main__":
    unittest.main()
