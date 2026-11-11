import json
import http.server
import contextlib
import io
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import check_health as health
import check_subscriptions as subscriptions


class FakeClient:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def request(self, url, method="GET", limit=health.TEXT_LIMIT, partial=False):
        self.calls.append((method, url))
        response = self.routes[(method, url)]
        if isinstance(response, Exception):
            raise response
        return health.Response(url, *response)


def reply(value, content_type="application/json"):
    body = json.dumps(value).encode() if isinstance(value, dict) else value
    return 200, {"content-type": content_type}, body, 12


class HealthTests(unittest.TestCase):
    site = {"name": "合成站", "api": "https://catalog.example/vod?token=public&ac=list"}

    def client(self, entries=None, search=None):
        entries = entries if entries is not None else [{
            "vod_id": 7, "vod_name": "合成剧", "vod_pic": "https://cover.example/a.jpg",
            "vod_play_url": "第一集$https://media.example/video",
        }]
        catalog = health.api_url(self.site["api"], ac="detail", pg="1")
        search_url = health.api_url(self.site["api"], ac="detail", pg="1", wd="合成剧")
        return FakeClient({
            ("GET", catalog): reply({"code": 1, "list": entries}),
            ("GET", search_url): reply({"code": 1, "list": entries if search is None else search}),
            ("HEAD", "https://cover.example/a.jpg"): reply(b"", "image/jpeg"),
            ("GET", "https://media.example/video"): reply(b"synthetic media", "video/mp4"),
        })

    def test_directory_search_cover_and_decode_are_separate(self):
        client = self.client()
        with patch.object(health, "decode_frame", return_value=True):
            result = health.probe_site("film-tv", "sample", self.site, client, "ffmpeg")
        self.assertEqual([result[field].status for field in health.FIELDS], ["ok"] * 4)
        self.assertEqual(result["catalog"].ms, 12)
        self.assertEqual([method for method, url in client.calls if "cover.example" in url], ["HEAD"])

    def test_decoder_failure_is_not_playable(self):
        with patch.object(health, "decode_frame", return_value=False):
            result = health.probe_site("film-tv", "sample", self.site, self.client(), "ffmpeg")
        self.assertEqual(result["playback"].status, "fail")

    def test_cover_head_unsupported_is_unknown_without_get_fallback(self):
        client = self.client()
        client.routes[("HEAD", "https://cover.example/a.jpg")] = health.HTTPStatusError(405)
        result = health.probe_site("film-tv", "sample", self.site, client, None)
        self.assertEqual(result["cover"].status, "unknown")
        self.assertFalse(any(method == "GET" and "cover.example" in url for method, url in client.calls))

    def test_cover_failure_does_not_suppress_search_or_playback(self):
        client = self.client()
        client.routes[("HEAD", "https://cover.example/a.jpg")] = health.HTTPStatusError(403)
        with patch.object(health, "decode_frame", return_value=True):
            result = health.probe_site("film-tv", "sample", self.site, client, "ffmpeg")
        self.assertEqual(result["cover"].status, "fail")
        self.assertEqual(result["search"].status, "ok")
        self.assertEqual(result["playback"].status, "ok")

    def test_details_must_match_selected_media_identity(self):
        client = self.client(entries=[{"vod_id": 7, "vod_name": "合成剧"}])
        client.routes[("GET", health.api_url(self.site["api"], ac="detail", ids="7"))] = reply({
            "list": [{"vod_id": 8, "vod_name": "合成剧", "vod_pic": "https://bad.example/cover"}],
        })
        result = health.probe_site("film-tv", "sample", self.site, client, None)
        self.assertEqual(result["cover"].status, "fail")
        self.assertFalse(any("bad.example" in url for _, url in client.calls))

    def test_missing_decoder_is_unknown(self):
        result = health.probe_site("film-tv", "sample", self.site, self.client(), None)
        self.assertEqual(result["playback"].status, "unknown")

    def test_search_must_match_sample_identity_or_title(self):
        result = health.probe_site("film-tv", "sample", self.site,
                                   self.client(search=[{"vod_id": 9, "vod_name": "其他剧"}]), None)
        self.assertEqual(result["search"].status, "fail")

    def test_empty_directory_blocks_dependent_checks(self):
        result = health.probe_site("film-tv", "sample", self.site, self.client(entries=[]), None)
        self.assertEqual(result["catalog"].status, "fail")
        self.assertTrue(all(result[field].status == "unknown" for field in health.FIELDS[1:]))

    def test_native_adapter_dispatches_to_native_protocol_runner(self):
        client = FakeClient({})
        expected = health.initial_result("film-tv", "native", self.site)
        expected["catalog"] = health.Outcome("ok", "原生目录", 12)
        with patch.object(health, "probe_native", return_value=expected) as native:
            result = health.probe_site("film-tv", "native", {**self.site, "adapter": "cinejoy"}, client, None)
        self.assertEqual(result["catalog"].status, "ok")
        native.assert_called_once()
        self.assertEqual(client.calls, [])

    def test_api_query_preserves_meaning_and_escaped_path(self):
        url = health.api_url("https://api.example/a%2Fb?token=x%2By&wd=old&pg=8&ac=list", ac="detail", pg="1")
        self.assertIn("/a%2Fb?", url)
        self.assertIn("token=x%2By", url)
        self.assertNotIn("wd=", url)
        self.assertNotIn("pg=8", url)

    def test_xml_and_json_are_parsed_with_identity(self):
        body = b'<rss><list><video><id>7</id><name>Demo</name><pic>https://a.example/a</pic><dl><dd flag="main">E1$https://v.example/a</dd></dl></video></list></rss>'
        self.assertEqual(health.parse_catalog(body)[0]["vod_id"], "7")
        for invalid in (b'<!DOCTYPE rss [<!ENTITY a "x">]><rss><list/></rss>',
                        b'<html><list/></html>', b'{"code":0,"list":[]}',
                        b'{"list":[{"vod_id":true,"vod_name":"X"}]}'):
            with self.subTest(invalid=invalid), self.assertRaises(health.ProbeError):
                health.parse_catalog(invalid)

    def test_private_targets_and_dns_rebinding_are_rejected(self):
        for url in ("file:///etc/passwd", "http://user:pass@public.example/", "http://127.0.0.1/", "http://[::1]/"):
            with self.subTest(url=url), self.assertRaises((health.ProbeError, ValueError)):
                health.resolve_public(url)
        with patch.object(health.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.1", 80))]):
            with self.assertRaises(health.ProbeError):
                health.resolve_public("https://public.example/")

    def test_hls_uses_current_variant_init_and_one_segment(self):
        client = FakeClient({
            ("GET", "https://media.example/master"): reply(b'#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100\nlow/index\n#EXT-X-STREAM-INF:BANDWIDTH=200\nhigh/index\n', "application/vnd.apple.mpegurl"),
            ("GET", "https://media.example/low/index"): reply(b'#EXTM3U\n#EXT-X-MAP:URI="init"\n#EXTINF:4,\nseg\n#EXT-X-ENDLIST\n', "application/vnd.apple.mpegurl"),
            ("GET", "https://media.example/low/init"): reply(b"init", "video/mp4"),
            ("GET", "https://media.example/low/seg"): reply(b"segment", "video/mp4"),
        })
        with patch.object(health, "decode_frame", return_value=True) as decoder:
            outcome = health.probe_playback(client, "https://media.example/master", "ffmpeg")
        self.assertEqual(outcome.status, "ok")
        self.assertEqual(decoder.call_args.args[0], b"initsegment")
        self.assertFalse(any("high" in url for _, url in client.calls))

    def test_encrypted_and_byte_range_hls_are_unknown(self):
        for tag in (b'#EXT-X-KEY:METHOD=AES-128,URI="key"', b'#EXT-X-BYTERANGE:100@0',
                    b'#EXT-X-SESSION-KEY:METHOD=SAMPLE-AES,URI="key"'):
            client = FakeClient({("GET", "https://m.example/a"): reply(b'#EXTM3U\n' + tag + b'\n#EXTINF:4,\nseg\n')})
            result = health.probe_playback(client, "https://m.example/a", "ffmpeg")
            self.assertEqual(result.status, "unknown")
            self.assertEqual(len(client.calls), 1)

    def test_report_escapes_untrusted_names_and_keeps_readme_content(self):
        row = health.initial_result("film-tv", "id", {"name": '<img src="https://x">|\n# injected'})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "README.md"
            path.write_text("Original\n\n" + health.START + "\nold\n" + health.END + "\nTail\n", encoding="utf-8")
            health.write_report(path, [row], "2026-11-11T00:00:00+00:00", "未运行", None)
            report = path.read_text(encoding="utf-8")
        self.assertTrue(report.startswith("Original\n"))
        self.assertTrue(report.endswith("\nTail\n"))
        self.assertNotIn('<img src="https://x">', report)
        self.assertNotIn("\n# injected", report)
        self.assertNotIn("old\n", report)

    def test_malformed_report_markers_do_not_overwrite_readme(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "README.md"
            original = "Original\n" + health.START
            path.write_text(original, encoding="utf-8")
            with self.assertRaises(ValueError):
                health.write_report(path, [], "now", "none", None)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_failed_summary_write_preserves_previous_report(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "README.md"
            path.write_text("Previous report", encoding="utf-8")
            with self.assertRaises(OSError):
                health.write_report(path, [], "now", "none", Path(folder) / "missing" / "summary.md")
            self.assertEqual(path.read_text(encoding="utf-8"), "Previous report")

    def test_cli_updates_all_groups_without_changing_subscriptions(self):
        groups = dict(health.GROUPS)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "subscriptions").mkdir()
            (root / "README.md").write_text("Keep manual instructions\n" + health.INVENTORY_START + "\n" + health.INVENTORY_END + "\n", encoding="utf-8")
            for group in groups:
                (root / "subscriptions" / f"{group}.json").write_text(json.dumps({
                    "cache_time": 7200, "api_site": {group: {
                        "name": "Synthetic " + group.replace("-", " "),
                        "api": f"https://{group}.example/vod",
                    }},
                }), encoding="utf-8")
            before = {path: path.read_bytes() for path in (root / "subscriptions").glob("*.json")}

            class FixtureClient:
                def __init__(self, **kwargs):
                    pass

                def request(self, url, method="GET", **kwargs):
                    body = reply({"code": 1, "list": [{"vod_id": 7, "vod_name": "Synthetic",
                        "vod_pic": "https://cover.example/a", "vod_play_url": "E1$https://media.example/a"}]})
                    if method == "HEAD":
                        body = reply(b"", "image/jpeg")
                    return health.Response(url, *body)

            with patch.object(health, "ROOT", root), patch.object(health, "GROUPS", groups), \
                    patch.object(subscriptions, "GROUPS", groups), patch.object(health, "Client", FixtureClient), \
                    patch.object(health.shutil, "which", return_value=None), \
                    patch("sys.argv", ["check_health.py", "--workers", "2", "--summary", str(root / "summary.md")]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(health.main(), 0)
            report = (root / "README.md").read_text(encoding="utf-8")
            self.assertIn("共 4 项", report)
            self.assertIn("Keep manual instructions", report)
            self.assertEqual(report.count("✅ 有效目录"), 4)
            self.assertEqual(report.count("未安装 FFmpeg，未验证首帧"), 4)
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            self.assertNotIn("Keep manual instructions", (root / "summary.md").read_text(encoding="utf-8"))

    def test_removed_rows_and_inventory_counts_are_replaced_from_current_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "README.md"
            path.write_text(health.INVENTORY_START + "\nold inventory\n" + health.INVENTORY_END + "\n", encoding="utf-8")
            first = [("film-tv", "old", {"name": "Removed"}), ("film-tv", "keep", {"name": "Kept"})]
            health.write_report(path, [health.initial_result(*row) for row in first], "first", "none", None, first)
            current = [("animation", "new", {"name": "Added"})]
            health.write_report(path, [health.initial_result(*row) for row in current], "second", "none", None, current)
            text = path.read_text(encoding="utf-8")
        self.assertNotIn("Removed", text)
        self.assertNotIn("Kept", text)
        self.assertIn("Added", text)
        self.assertIn("动漫（1 项）", text)
        self.assertIn("影视（0 项）", text)
        self.assertIn("1 项订阅来源", text)

    def test_native_results_are_validated_and_not_inferred_from_http(self):
        payload = {field: {"status": "ok", "message": "Native", "ms": 12} for field in health.FIELDS}
        completed = subprocess.CompletedProcess([], 0, b"YINGCHUAN_HEALTH " + json.dumps(payload).encode() + b"\nPASS\n")
        with patch.object(health.subprocess, "run", return_value=completed) as runner:
            result = health.probe_native("film-tv", "cinejoy", {**self.site, "adapter": "cinejoy"}, None, "/fixture/runner")
        self.assertEqual(result["playback"].status, "ok")
        sent = json.loads(runner.call_args.kwargs["input"])
        self.assertEqual(sent["site"]["adapter"], "cinejoy")
        self.assertNotIn("GH_TOKEN", runner.call_args.kwargs["env"])
        payload["playback"]["status"] = "pretend"
        completed.stdout = b"YINGCHUAN_HEALTH " + json.dumps(payload).encode()
        with patch.object(health.subprocess, "run", return_value=completed), self.assertRaisesRegex(RuntimeError, "状态无效"):
            health.probe_native("film-tv", "cinejoy", self.site, None, "/fixture/runner")


class LocalHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls = []

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def handle(self):
                try:
                    super().handle()
                except ConnectionError:
                    pass

            def log_message(self, *args):
                pass

            def do_HEAD(self):
                self.serve()

            def do_GET(self):
                self.serve()

            def serve(self):
                cls.calls.append((self.command, self.path, dict(self.headers)))
                if self.path == "/slow-headers":
                    for character in b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n":
                        self.wfile.write(bytes([character]))
                        self.wfile.flush()
                        threading.Event().wait(0.02)
                    return
                if self.path == "/private":
                    self.send_response(302)
                    self.send_header("Location", "http://127.0.0.1/private-target")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/payload")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if self.path == "/forbidden":
                    self.send_response(403)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                payload = b"synthetic-image" if self.path == "/image" else b"bounded-body"
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg" if self.path == "/image" else "text/plain")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(payload)

        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.calls.clear()

        def resolve(url):
            parsed = health.public_url(url)
            return parsed, (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", self.server.server_address)

        self.resolver = patch.object(health, "resolve_public", side_effect=resolve)
        self.resolver.start()
        self.addCleanup(self.resolver.stop)

    def test_real_http_redirect_keeps_head_and_never_sends_credentials(self):
        response = health.Client().request("http://fixture.example/redirect", method="HEAD")
        self.assertEqual(response.body, b"")
        self.assertEqual([method for method, _, _ in self.calls], ["HEAD", "HEAD"])
        for _, _, headers in self.calls:
            self.assertNotIn("Cookie", headers)
            self.assertNotIn("Authorization", headers)

    def test_redirect_private_address_is_rejected_before_connection(self):
        with self.assertRaises(health.ProbeError):
            health.Client().request("http://fixture.example/private")
        self.assertEqual([path for _, path, _ in self.calls], ["/private"])

    def test_body_size_and_partial_sample_are_bounded(self):
        with self.assertRaisesRegex(health.ProbeError, "大小上限"):
            health.Client().request("http://fixture.example/payload", limit=4)
        response = health.Client().request("http://fixture.example/payload", limit=4, partial=True)
        self.assertEqual(response.body, b"boun")
        self.assertEqual(self.calls[-1][2]["Range"], "bytes=0-3")

    def test_image_get_is_rejected_but_head_works(self):
        client = health.Client()
        with self.assertRaisesRegex(health.ProbeError, "禁止读取图片正文"):
            client.request("http://fixture.example/image")
        self.assertEqual(client.request("http://fixture.example/image", method="HEAD").body, b"")

    def test_http_denial_is_preserved(self):
        with self.assertRaisesRegex(health.HTTPStatusError, "HTTP 403"):
            health.Client().request("http://fixture.example/forbidden")

    def test_exhausted_budget_sends_no_request(self):
        client = health.Client(budget=-1)
        with self.assertRaisesRegex(health.ProbeError, "预算用尽"):
            client.request("http://fixture.example/payload")
        self.assertEqual(self.calls, [])

    def test_slow_header_trickle_cannot_extend_request_budget(self):
        started = time.monotonic()
        with self.assertRaises(health.ProbeError):
            health.Client(timeout=0.1).request("http://fixture.example/slow-headers")
        self.assertLess(time.monotonic() - started, 0.6)


class DecoderTests(unittest.TestCase):
    def test_synthetic_video_decodes_and_invalid_data_does_not(self):
        executable = shutil.which("ffmpeg")
        if not executable:
            self.fail("合成首帧回归需要 PATH 中的 FFmpeg")
        media = subprocess.run([
            executable, "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", "color=c=black:s=64x64:r=10", "-t", "2", "-c:v", "mpeg2video",
            "-threads", "1", "-f", "mpegts", "pipe:1",
        ], capture_output=True, timeout=10, check=True).stdout
        self.assertTrue(health.decode_frame(media, executable))
        self.assertFalse(health.decode_frame(b"not a video", executable))


if __name__ == "__main__":
    unittest.main()
