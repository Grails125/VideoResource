import argparse
import ipaddress
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "film-tv": "影视",
    "short-drama": "短剧",
    "animation": "动漫",
    "unknown": "未知",
}
ADAPTERS = {
    "tencent", "hanxiaoquan", "guipian", "cinejoy", "movy",
    "huangdou", "huangju", "yeguo", "huangguoai", "jinguo", "jinguoduanju",
    "sorani", "dsd", "huangguo-video", "cloudfront", "heitao", "beabox",
}
BUILTIN_ADAPTERS = {"bilibili", "hongguo", "kanju51", "jianpian", "netflixgc"}
NAME_BLOCKS = re.compile(r"\[[^\[\]]*\]|［[^［］]*］|【[^【】]*】|\([^()]*\)|（[^（）]*）")
NAME_LATENCY = re.compile(
    r"(?:测速|延迟|耗时|响应(?:时间)?)?\s*[:：]?\s*"
    r"(?<![A-Za-z0-9])\d+(?:\.\d+)?\s*(?:毫秒(?:钟)?|msec|ms)(?![A-Za-z])",
    re.IGNORECASE,
)


def clean_source_name(value):
    value = unicodedata.normalize("NFC", value).replace("🔞", " ")
    value = NAME_BLOCKS.sub(lambda match: " " if NAME_LATENCY.search(match[0]) else match[0], value)
    value = NAME_LATENCY.sub(" ", value)
    plain = []
    for character in value:
        codepoint = ord(character)
        if (unicodedata.category(character) == "Cf" or character == "\u20e3"
                or 0xFE00 <= codepoint <= 0xFE0F or 0xE0100 <= codepoint <= 0xE01EF):
            continue
        plain.append(character if unicodedata.category(character)[0] in {"L", "N", "M"} else " ")
    return " ".join("".join(plain).split()).removeprefix("成人 ")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    body = path.read_bytes()
    if len(body) > 2 * 1024 * 1024:
        raise ValueError("Subscription exceeds client document limit")
    return json.loads(body.decode("utf-8-sig"), object_pairs_hook=unique_object)


def public_url(value):
    if not isinstance(value, str) or not value or re.search(r"[\s\\\x00-\x1f\x7f]", value):
        raise ValueError("Invalid public source URL")
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None or parsed.fragment):
        raise ValueError("Invalid public source URL")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid source URL port")
    if parsed.netloc.endswith(":"):
        raise ValueError("Invalid source URL port")
    hostname = parsed.hostname.lower().rstrip(".")
    if (hostname in {"localhost", "localhost.localdomain"}
            or hostname.endswith((".localhost", ".local", ".localdomain"))):
        raise ValueError("Source URL points to a local hostname")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Source URL points to a non-public address")
    return parsed


def source_identity(site):
    if not isinstance(site, dict) or set(site) - {"name", "api", "detail", "disabled", "adapter", "native"}:
        raise ValueError("Invalid source schema")
    if not isinstance(site.get("name"), str) or not site["name"].strip():
        raise ValueError("Source name is required")
    if site["name"] != clean_source_name(site["name"]):
        raise ValueError("Source name must use plain words and numbers without decoration or latency")
    parsed = public_url(site.get("api"))
    if "disabled" in site and type(site["disabled"]) is not bool:
        raise ValueError("Disabled state must be boolean")
    if site.get("disabled", False):
        raise ValueError("Published sources must be enabled by default")
    detail = site.get("detail", "")
    if not isinstance(detail, str):
        raise ValueError("Detail endpoint must be a string")
    if detail:
        public_url(detail)
    if "adapter" in site:
        adapter = site["adapter"]
        if isinstance(adapter, str) and adapter in BUILTIN_ADAPTERS:
            raise ValueError("Built-in adapters do not belong in source subscriptions")
        if not isinstance(adapter, str) or adapter not in ADAPTERS:
            raise ValueError("Unsupported native adapter")
        native = site.get("native")
        if not isinstance(native, dict) or type(native.get("version")) is not int or native["version"] != 1:
            raise ValueError("Native configuration must use version 1")
        return "native", adapter
    if "native" in site:
        raise ValueError("Native configuration requires an adapter")
    hostname = parsed.hostname.lower().rstrip(".")
    authority = f"[{hostname}]" if ":" in hostname else hostname
    if parsed.port is not None and parsed.port != {"http": 80, "https": 443}[parsed.scheme]:
        authority += f":{parsed.port}"
    query = defaultdict(list)
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        query[key].append(value)
    if query.get("ac", [None])[0] == "list":
        query.pop("ac")
    encoded_query = urlencode([(key, value) for key in sorted(query) for value in query[key]])
    address = urlunsplit((parsed.scheme, authority, parsed.path.rstrip("/"), encoded_query, ""))
    return "api", address, detail


def check(root=ROOT):
    root = Path(root).resolve()
    expected = {f"subscriptions/{group}.json" for group in GROUPS}
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() == ".json"
        and ".git" not in path.relative_to(root).parts
    }
    if actual != expected:
        raise ValueError(f"Only the four subscription JSON files are allowed; missing={sorted(expected - actual)}, extra={sorted(actual - expected)}")
    keys, identities, summary = set(), set(), {}
    native_sources = 0
    names = defaultdict(list)
    for group, name in GROUPS.items():
        path = root / "subscriptions" / f"{group}.json"
        if path.is_symlink():
            raise ValueError("Subscription must be a regular repository file")
        document = read_json(path)
        if (not isinstance(document, dict) or set(document) != {"cache_time", "api_site"}
                or type(document["cache_time"]) is not int or document["cache_time"] != 7200
                or not isinstance(document["api_site"], dict)):
            raise ValueError("Invalid subscription envelope")
        sites = document["api_site"]
        if len(sites) > 256:
            raise ValueError(f"Subscription exceeds 256 source entries: {group}")
        for key, site in sites.items():
            if not key or re.search(r"[\s\x00-\x1f\x7f]", key):
                raise ValueError("Invalid stable source key")
            identity = source_identity(site)
            native_sources += identity[0] == "native"
            if key in keys or identity in identities:
                raise ValueError(f"Duplicate source across subscriptions: {key}")
            keys.add(key)
            identities.add(identity)
            names[site["name"]].append(f"{group}:{key}")
        summary[name] = {"sources": len(sites), "disabled": 0}
    return {"status": "PASSED", "files": len(expected), "sources": len(keys), "native_sources": native_sources, "groups": summary,
            "duplicate_names": {name: entries for name, entries in names.items() if len(entries) > 1}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", type=Path)
    options = parser.parse_args()
    result = check()
    if options.github_output:
        with options.github_output.open("a", encoding="utf-8") as output:
            output.write(f"native={'true' if result['native_sources'] else 'false'}\nsources={result['sources']}\nnative_sources={result['native_sources']}\n")
    print(json.dumps(result, ensure_ascii=False))
