import argparse
import concurrent.futures
import dataclasses
import datetime
import html
import http.client
import ipaddress
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from check_subscriptions import BUILTIN_ADAPTERS, GROUPS, ROOT, check, public_url, read_json


TEXT_LIMIT = 2 * 1024 * 1024
MEDIA_LIMIT = 1024 * 1024
FIELDS = ("catalog", "cover", "search", "playback")
START = "<!-- source-health:start -->"
END = "<!-- source-health:end -->"
INVENTORY_START = "<!-- source-inventory:start -->"
INVENTORY_END = "<!-- source-inventory:end -->"


class ProbeError(Exception):
    pass


class HTTPStatusError(ProbeError):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status = status


@dataclasses.dataclass
class Outcome:
    status: str
    message: str
    ms: int | None = None


@dataclasses.dataclass
class Response:
    url: str
    status: int
    headers: dict
    body: bytes
    ms: int


def resolve_public(url):
    parsed = public_url(url)
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80),
                                   type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ProbeError("拒绝非公网目标")
    return parsed, addresses[0]


class Client:
    def __init__(self, timeout=8, budget=50):
        self.timeout = timeout
        self.deadline = time.monotonic() + budget
        self.remaining = 16

    def request(self, url, method="GET", limit=TEXT_LIMIT, partial=False):
        started = time.monotonic()
        for _ in range(4):
            self.remaining -= 1
            if self.remaining < 0 or time.monotonic() >= self.deadline:
                raise ProbeError("来源检测预算用尽")
            connection = None
            response = None
            timer = None
            try:
                parsed, address = resolve_public(url)
                timeout = min(self.timeout - (time.monotonic() - started), self.deadline - time.monotonic())
                if timeout <= 0:
                    raise ProbeError("来源检测超时")
                family, kind, protocol, _, target = address

                def connect(*args, **kwargs):
                    sock = socket.socket(family, kind, protocol)
                    try:
                        sock.settimeout(timeout)
                        sock.connect(target)
                        return sock
                    except BaseException:
                        sock.close()
                        raise

                connection_type = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
                connection = connection_type(parsed.hostname, port=parsed.port, timeout=timeout)
                connection._create_connection = connect
                connection.connect()
                transport = connection.sock

                def abort_request(sock=transport):
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

                timer = threading.Timer(max(0.001, min(self.deadline, started + self.timeout) - time.monotonic()),
                                        abort_request)
                timer.daemon = True
                timer.start()
                headers = {"User-Agent": "YingChuan-Source-Health/1.0", "Accept-Encoding": "identity"}
                if partial:
                    headers["Range"] = f"bytes=0-{limit - 1}"
                connection.request(method, urlunsplit(("", "", parsed.path or "/", parsed.query, "")), headers=headers)
                response = connection.getresponse()
                response_headers = {key.lower(): value for key, value in response.getheaders()}
                if response.status in {301, 302, 303, 307, 308}:
                    location = response_headers.get("location")
                    if not location:
                        raise ProbeError("重定向缺少地址")
                    next_url = urljoin(url, location)
                    if parsed.scheme == "https" and urlsplit(next_url).scheme != "https":
                        raise ProbeError("拒绝 HTTPS 降级")
                    url = next_url
                    continue
                if response.status not in {200, 206}:
                    raise HTTPStatusError(response.status)
                if response_headers.get("content-encoding", "identity").lower() != "identity":
                    raise ProbeError("不支持压缩响应")
                body = bytearray()
                if method != "HEAD":
                    if response_headers.get("content-type", "").lower().startswith("image/"):
                        raise ProbeError("禁止读取图片正文")
                    maximum = limit if partial else limit + 1
                    request_deadline = min(self.deadline, started + self.timeout)
                    while len(body) < maximum:
                        if time.monotonic() >= request_deadline:
                            raise ProbeError("响应读取超时")
                        chunk = response.read1(min(65536, maximum - len(body)))
                        if not chunk:
                            break
                        body.extend(chunk)
                    if not partial and len(body) > limit:
                        raise ProbeError("响应超过大小上限")
                return Response(url, response.status, response_headers, bytes(body),
                                round((time.monotonic() - started) * 1000))
            except ssl.SSLError:
                raise ProbeError("TLS 验证失败") from None
            except (OSError, http.client.HTTPException, ValueError):
                raise ProbeError("网络错误或地址无效") from None
            finally:
                if timer:
                    timer.cancel()
                if response:
                    response.close()
                if connection:
                    connection.close()
        raise ProbeError("重定向超过上限")


def api_url(base, **parameters):
    parsed = urlsplit(base)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if key not in {"ac", "pg", "wd", "ids"}]
    if "/xml" in parsed.path.lower() and parameters.get("ac") == "detail":
        parameters["ac"] = "videolist"
    query.extend(parameters.items())
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))


def parse_catalog(body):
    if len(body) > TEXT_LIMIT:
        raise ProbeError("目录响应过大")
    try:
        text = body.decode("utf-8-sig")
        if text.lstrip().startswith("<"):
            if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.I):
                raise ProbeError("拒绝 XML DTD 或实体")
            root = ET.fromstring(text)
            listing = root.find("list")
            if root.tag != "rss" or listing is None:
                raise ProbeError("XML 不是采集目录")
            if sum(1 for _ in root.iter()) > 20000:
                raise ProbeError("XML 结构过大")
            rows = [{
                "vod_id": video.findtext("id", ""), "vod_name": video.findtext("name", ""),
                "vod_pic": video.findtext("pic", ""),
                "vod_play_url": "$$$".join(line.text or "" for line in video.findall("dl/dd")),
            } for video in listing.findall("video")]
        else:
            document = json.loads(text)
            if not isinstance(document, dict) or document.get("code", 1) not in {1, "1", 200, "200"}:
                raise ProbeError("采集接口返回错误")
            rows = document.get("list")
        if not isinstance(rows, list) or len(rows) > 500:
            raise ProbeError("目录条目结构无效或超过上限")
        for row in rows:
            if (not isinstance(row, dict) or type(row.get("vod_id")) not in {int, str}
                    or not str(row["vod_id"]).strip() or not isinstance(row.get("vod_name"), str)
                    or not row["vod_name"].strip()):
                raise ProbeError("目录缺少有效媒体身份")
        return rows
    except (ValueError, UnicodeError, ET.ParseError, RecursionError, TypeError):
        raise ProbeError("无法解析采集目录") from None


def decode_frame(body, executable):
    try:
        result = subprocess.run([
            executable, "-nostdin", "-hide_banner", "-loglevel", "error", "-max_alloc", "67108864",
            "-protocol_whitelist", "pipe", "-format_whitelist", "mpegts,mpeg,mov,matroska,flv,avi",
            "-probesize", str(2 * MEDIA_LIMIT),
            "-analyzeduration", "2000000", "-threads", "1", "-i", "pipe:0", "-map", "0:v:0",
            "-frames:v", "1", "-threads", "1", "-f", "null", "-progress", "pipe:1", "-",
        ], input=body, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=False)
        return result.returncode == 0 and re.search(rb"(?:^|\n)frame=\s*[1-9]\d*\s*(?:\n|$)", result.stdout) is not None
    except subprocess.TimeoutExpired:
        raise ProbeError("首帧解码超时") from None
    except OSError:
        raise ProbeError("无法运行 FFmpeg") from None


def probe_playback(client, url, executable):
    if not executable:
        return Outcome("unknown", "未安装 FFmpeg，未验证首帧")
    started = time.monotonic()
    for _ in range(3):
        response = client.request(url, limit=MEDIA_LIMIT, partial=True)
        body = response.body
        stripped = body.lstrip(b"\xef\xbb\xbf \r\n\t")
        if stripped.startswith(b"#EXTM3U"):
            if len(body) >= MEDIA_LIMIT:
                return Outcome("unknown", "HLS 清单超过探测上限")
            text = stripped.decode("utf-8-sig", errors="strict")
            if any(tag in text for tag in ("#EXT-X-SESSION-KEY:", "#EXT-X-BYTERANGE:", "#EXT-X-PART:")):
                return Outcome("unknown", "加密或分段范围清单需客户端验证")
            if any(not re.search(r"(?:^|,)METHOD=NONE(?:,|$)", line.split(":", 1)[1])
                   for line in text.splitlines() if line.startswith("#EXT-X-KEY:")):
                return Outcome("unknown", "加密流需客户端验证")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            variants = [lines[index + 1] for index, line in enumerate(lines[:-1])
                        if line.startswith("#EXT-X-STREAM-INF:") and not lines[index + 1].startswith("#")]
            if variants:
                url = urljoin(response.url, variants[0])
                continue
            segments = [lines[index + 1] for index, line in enumerate(lines[:-1])
                        if line.startswith("#EXTINF:") and not lines[index + 1].startswith("#")]
            if not segments:
                raise ProbeError("HLS 缺少完整媒体分片")
            initialization = b""
            first_segment = next(index for index, line in enumerate(lines) if line.startswith("#EXTINF:"))
            maps = [line for line in lines[:first_segment] if line.startswith("#EXT-X-MAP:")]
            if maps:
                if "BYTERANGE=" in maps[-1]:
                    return Outcome("unknown", "初始化范围需客户端验证")
                match = re.search(r'URI="([^"]+)"', maps[-1])
                if not match:
                    raise ProbeError("HLS 初始化地址无效")
                initialization = client.request(urljoin(response.url, match[1]), limit=MEDIA_LIMIT).body
            segment = client.request(urljoin(response.url, segments[0]), limit=MEDIA_LIMIT, partial=True).body
            body = initialization + segment
        elif stripped.startswith((b"<", b"{")):
            return Outcome("unknown", "网页、解析或 DASH 协议需客户端验证")
        if not body or not decode_frame(body, executable):
            return Outcome("fail", "有界样本未解码首帧", round((time.monotonic() - started) * 1000))
        return Outcome("ok", "抽样首帧", round((time.monotonic() - started) * 1000))
    return Outcome("unknown", "HLS 层级超过探测上限")


def initial_result(group, key, site, reason="待检测"):
    return {"group": group, "key": key, "name": site["name"],
            **{field: Outcome("unknown", reason) for field in FIELDS}}


def safe_probe(action):
    started = time.monotonic()
    try:
        return action()
    except ProbeError as error:
        return Outcome("fail", str(error), round((time.monotonic() - started) * 1000))
    except (ValueError, UnicodeError, TypeError):
        return Outcome("fail", "响应字段无效", round((time.monotonic() - started) * 1000))


def probe_native(group, key, site, executable, runner=None):
    runner = runner or os.environ.get("YINGCHUAN_NATIVE_PROBE")
    if not runner:
        raise RuntimeError("原生检测器未准备，请先构建客户端协议检测程序")
    with tempfile.TemporaryDirectory(prefix="yingchuan-native-health-") as state:
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LD_LIBRARY_PATH", "SSL_CERT_FILE", "SSL_CERT_DIR"}}
        environment.update({"HOME": state, "USERPROFILE": state,
                            "YINGCHUAN_HEALTH_RUN": "1", "YINGCHUAN_HEALTH_FFMPEG": executable or ""})
        try:
            process = subprocess.run([str(runner), "-test.run=^TestSourceHealthProbe$", "-test.timeout=90s"],
                                     input=json.dumps({"version": 1, "key": key, "site": site}).encode(),
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     env=environment, timeout=85, check=True)
        except subprocess.TimeoutExpired:
            raise RuntimeError("原生检测进程超时，阶段未确认；原报告保留") from None
    lines = [line.removeprefix(b"YINGCHUAN_HEALTH ") for line in process.stdout.splitlines()
             if line.startswith(b"YINGCHUAN_HEALTH ")]
    if len(lines) != 1 or len(lines[0]) > 16384:
        raise RuntimeError("原生检测器输出无效，原报告保留")
    payload = json.loads(lines[0])
    if not isinstance(payload, dict) or set(payload) != set(FIELDS):
        raise RuntimeError("原生检测字段无效")
    result = initial_result(group, key, site)
    for field in FIELDS:
        entry = payload[field]
        if (not isinstance(entry, dict) or set(entry) - {"status", "message", "ms"}
                or entry.get("status") not in {"ok", "fail", "unknown"}
                or not isinstance(entry.get("message"), str) or len(entry["message"]) > 160
                or entry.get("ms") is not None and (type(entry["ms"]) is not int or not 0 <= entry["ms"] <= 85000)):
            raise RuntimeError("原生检测状态无效")
        result[field] = Outcome(**entry)
    return result


def probe_site(group, key, site, client, executable, native_runner=None):
    result = initial_result(group, key, site, "目录不可用，未检测")
    if site.get("adapter"):
        return probe_native(group, key, site, executable, native_runner)
    rows = []

    def catalog():
        response = client.request(api_url(site["api"], ac="detail", pg="1"))
        rows.extend(parse_catalog(response.body))
        if not rows:
            raise ProbeError("目录为空，无法抽样")
        return Outcome("ok", "有效目录", response.ms)

    result["catalog"] = safe_probe(catalog)
    if result["catalog"].status != "ok":
        return result
    sample = rows[0]

    def search():
        response = client.request(api_url(site["api"], ac="detail", pg="1", wd=sample["vod_name"][:80]))
        matches = parse_catalog(response.body)
        if not any(str(row["vod_id"]) == str(sample["vod_id"]) or row["vod_name"] == sample["vod_name"] for row in matches):
            raise ProbeError("搜索未返回抽样条目")
        return Outcome("ok", "命中抽样条目", response.ms)

    result["search"] = safe_probe(search)
    if not sample.get("vod_pic") or not sample.get("vod_play_url"):
        def detail():
            response = client.request(api_url(site["api"], ac="detail", ids=str(sample["vod_id"])))
            matches = parse_catalog(response.body)
            match = next((row for row in matches if str(row["vod_id"]) == str(sample["vod_id"])), None)
            if match is None:
                raise ProbeError("详情未返回同一媒体")
            sample.update({field: value for field, value in match.items() if value})
            return Outcome("ok", "详情补全")
        detail_outcome = safe_probe(detail)
        if detail_outcome.status != "ok":
            for field, property_name in (("cover", "vod_pic"), ("playback", "vod_play_url")):
                if not sample.get(property_name):
                    result[field] = detail_outcome

    def cover():
        address = sample.get("vod_pic")
        if not isinstance(address, str) or not address.strip():
            return Outcome("unknown", "未提供封面地址")
        try:
            response = client.request(urljoin(site["api"], address.strip()), method="HEAD")
        except HTTPStatusError as error:
            if error.status in {405, 501}:
                return Outcome("unknown", "站点不支持 HEAD，未读取图片")
            raise
        content_type = response.headers.get("content-type", "").lower().split(";", 1)[0]
        if response.headers.get("content-length", "").strip() == "0":
            return Outcome("fail", "封面响应声明为空", response.ms)
        if not content_type.startswith("image/"):
            return Outcome("unknown", "封面响应头非图片，未读取正文", response.ms)
        return Outcome("ok", "仅 HEAD 可达", response.ms)

    if result["cover"].status == "unknown":
        result["cover"] = safe_probe(cover)

    def playback():
        raw = sample.get("vod_play_url")
        if not isinstance(raw, str) or not raw.strip():
            return Outcome("unknown", "未提供播放地址")
        episode = raw.split("$$$", 1)[0].split("#", 1)[0].strip()
        address = episode.split("$", 1)[-1].strip()
        return probe_playback(client, urljoin(site["api"], address), executable)

    if result["playback"].status == "unknown":
        result["playback"] = safe_probe(playback)
    return result


def escape(value):
    value = " ".join(str(value).split())
    value = re.sub(r"[\x00-\x1f\x7f]", "", value)
    return html.escape(value, quote=True).replace("|", "&#124;").replace("`", "&#96;").replace("[", "&#91;").replace("]", "&#93;").replace("*", "&#42;").replace("_", "&#95;")


def render_report(rows, checked_at, decoder_version):
    passed = sum(all(row[field].status == "ok" for field in FIELDS) for row in rows)
    failed = sum(any(row[field].status == "fail" for field in FIELDS) for row in rows)
    lines = [START, "", f"检测时间：{escape(checked_at)}；共 {len(rows)} 项，四项通过 {passed} 项，含失败 {failed} 项。",
             "", f"解码工具：{escape(decoder_version)}。延迟为运行节点的目录请求耗时（含 DNS、TLS 与正文），不代表本地延迟。",
             "", "✅ 通过 · ❌ 失败 · ⚪ 未验证。封面仅检查 HEAD；播放仅抽样一条线路的第一集和一个片段，首帧通过不保证整片、其他线路、音轨或设备可播。未验证和失败都不会禁用来源。", ""]
    for group, name in GROUPS.items():
        count = sum(row["group"] == group for row in rows)
        lines += [f"### {name}（{count} 项）", "", "| 站点 / 稳定键 | 目录 | 封面 | 搜索 | 能否播放 | 目录延迟 |",
                  "| --- | --- | --- | --- | --- | ---: |"]
        for row in rows:
            if row["group"] != group:
                continue
            cells = [f"{escape(row['name'])} · {escape(row['key'])}"]
            for field in FIELDS:
                outcome = row[field]
                marker = {"ok": "✅", "fail": "❌", "unknown": "⚪"}[outcome.status]
                duration = f" · {outcome.ms} ms" if field != "catalog" and outcome.ms is not None else ""
                cells.append(f"{marker} {escape(outcome.message)}{duration}")
            cells.append(f"{row['catalog'].ms} ms" if row["catalog"].ms is not None else "—")
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines + [END])


def inventory_report(sites):
    lines = [INVENTORY_START, "", "| 分类 | 订阅地址 | 来源数 |", "| --- | --- | ---: |"]
    for group, name in GROUPS.items():
        count = sum(candidate == group for candidate, _, _ in sites)
        address = f"https://raw.githubusercontent.com/yingchuan-media/yingchuan-sources/main/subscriptions/{group}.json"
        lines.append(f"| {name} | [subscriptions/{group}.json]({address}) | {count} |")
    lines += ["", f"当前共 **{len(sites)} 项订阅来源，全部默认启用**。数量和检测清单从四份 JSON 逐次生成，随来源新增、移除及名称变更更新。", "", INVENTORY_END]
    return "\n".join(lines)


def write_report(path, rows, checked_at, decoder_version, summary, sites=None):
    original = path.read_text(encoding="utf-8")
    if original.count(START) != original.count(END) or original.count(START) > 1:
        raise ValueError("README 检测区标记损坏")
    report = render_report(rows, checked_at, decoder_version)
    if START in original:
        begin, end = original.index(START), original.index(END)
        if end < begin:
            raise ValueError("README 检测区标记顺序错误")
        updated = original[:begin] + report + original[end + len(END):]
    else:
        updated = original.rstrip() + "\n\n" + report + "\n"
    if sites is not None:
        if updated.count(INVENTORY_START) != 1 or updated.count(INVENTORY_END) != 1:
            raise ValueError("README 订阅统计标记损坏")
        begin, end = updated.index(INVENTORY_START), updated.index(INVENTORY_END)
        if end < begin:
            raise ValueError("README 订阅统计标记顺序错误")
        updated = updated[:begin] + inventory_report(sites) + updated[end + len(INVENTORY_END):]
    if summary:
        Path(summary).write_text(report.replace(START, "").replace(END, ""), encoding="utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=".health-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(updated)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="检测四份站源订阅并原子更新 README，不修改订阅。")
    parser.add_argument("--initialize", action="store_true", help="仅生成未检测表格，不访问网络")
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=6)
    parser.add_argument("--timeout", type=int, choices=range(2, 16), default=8)
    parser.add_argument("--summary", type=Path, help="同时输出 GitHub Actions Markdown 摘要")
    parser.add_argument("--native-probe", type=Path, default=os.environ.get("YINGCHUAN_NATIVE_PROBE"), help="客户端原生协议检测程序")
    options = parser.parse_args()
    check(ROOT)
    sites = [(group, key, site) for group in GROUPS
             for key, site in read_json(ROOT / "subscriptions" / f"{group}.json")["api_site"].items()
             if site.get("adapter") not in BUILTIN_ADAPTERS]
    if not options.initialize and any(site.get("adapter") for _, _, site in sites) and not options.native_probe:
        raise RuntimeError("订阅含原生协议来源，必须准备 --native-probe；未覆盖旧报告")
    executable = shutil.which("ffmpeg")
    version = "未安装 FFmpeg"
    if options.initialize:
        rows = [initial_result(*site) for site in sites]
        checked_at, version = "本版配置尚未执行在线检测", "尚未执行"
    else:
        if executable:
            version = subprocess.run([executable, "-version"], capture_output=True, text=True, timeout=5, check=True).stdout.splitlines()[0]
        if any(site.get("adapter") for _, _, site in sites):
            version += "；原生协议核心 " + os.environ.get("YINGCHUAN_NATIVE_CORE_REVISION", "本地检测器")
        completed = 0
        progress_lock = threading.Lock()
        def run_site(site):
            nonlocal completed
            result = probe_site(*site, Client(timeout=options.timeout), executable, options.native_probe)
            with progress_lock:
                completed += 1
                states = " ".join(f"{field}={result[field].status}" for field in FIELDS)
                print(f"[{completed}/{len(sites)}] {site[0]}/{site[1]} {states}", flush=True)
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=options.workers) as pool:
            futures = [pool.submit(run_site, site) for site in sites]
            rows = [future.result() for future in futures]
        checked_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    write_report(ROOT / "README.md", rows, checked_at, version, options.summary, sites=sites)
    print(f"已更新 {len(rows)} 项检测信息；订阅配置未修改。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
