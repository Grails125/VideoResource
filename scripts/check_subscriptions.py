import ipaddress
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "film-tv": ("影视", 135),
    "short-drama": ("短剧", 6),
    "animation": ("动漫", 4),
    "unknown": ("未知", 62),
}
ADAPTERS = {
    "tencent", "jianpian", "hanxiaoquan", "guipian", "cinejoy", "movy",
    "huangdou", "huangju", "yeguo", "huangguoai", "jinguo", "jinguoduanju",
    "sorani", "dsd", "huangguo-video", "cloudfront", "heitao", "beabox",
}


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
        if not isinstance(adapter, str) or adapter not in ADAPTERS:
            raise ValueError("Unsupported native adapter")
        native = site.get("native")
        if native is None and "native" not in site and adapter == "jianpian":
            return "native", adapter
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
    for group, (name, count) in GROUPS.items():
        path = root / "subscriptions" / f"{group}.json"
        if path.is_symlink():
            raise ValueError("Subscription must be a regular repository file")
        document = read_json(path)
        if (not isinstance(document, dict) or set(document) != {"cache_time", "api_site"}
                or type(document["cache_time"]) is not int or document["cache_time"] != 7200
                or not isinstance(document["api_site"], dict)):
            raise ValueError("Invalid subscription envelope")
        sites = document["api_site"]
        if len(sites) != count:
            raise ValueError(f"Group count mismatch: {group}; expected {count}, got {len(sites)}")
        for key, site in sites.items():
            if not key or re.search(r"[\s\x00-\x1f\x7f]", key):
                raise ValueError("Invalid stable source key")
            identity = source_identity(site)
            if "🔞" in site["name"] and group != "unknown":
                raise ValueError("Explicit adult sources must remain in the unknown group")
            if key in keys or identity in identities:
                raise ValueError(f"Duplicate source across subscriptions: {key}")
            keys.add(key)
            identities.add(identity)
        summary[name] = {"sources": len(sites), "disabled": 0}
    return {"status": "PASSED", "files": len(expected), "sources": len(keys), "groups": summary}


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False))
