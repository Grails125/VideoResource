import hashlib
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    text = path.read_text(encoding="utf-8-sig")
    return text, json.loads(text, object_pairs_hook=unique_object)


def content_hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def source_identity(site):
    if site.get("adapter"):
        return "native", site["adapter"]
    parsed = urlsplit(site["api"].strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.fragment:
        raise ValueError("Invalid public source URL")
    authority = parsed.netloc.lower()
    if parsed.port == {"http": 80, "https": 443}[parsed.scheme]:
        authority = parsed.hostname.lower()
    query = defaultdict(list)
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        query[key].append(value)
    if query.get("ac", [None])[0] == "list":
        query.pop("ac")
    encoded_query = urlencode([(key, value) for key in sorted(query) for value in query[key]])
    address = urlunsplit((parsed.scheme, authority, parsed.path.rstrip("/"), encoded_query, ""))
    return "api", address, site.get("detail", "").strip()


def check():
    _, index = read_json(ROOT / "subscriptions/index.json")
    expected = {"film-tv": "影视", "short-drama": "短剧", "animation": "动漫", "unknown": "未知"}
    if [(group["id"], group["name"]) for group in index["groups"]] != list(expected.items()):
        raise ValueError("Subscriptions must use the four agreed content groups")
    legacy = {}
    for name, record in index["legacy_files"].items():
        path = (ROOT / name).resolve()
        if path.parent != ROOT:
            raise ValueError("Legacy path escapes repository root")
        _, document = read_json(path)
        if content_hash(document) != record["content_sha256"]:
            raise ValueError(f"Compatibility snapshot changed: {name}")
        if len(document["api_site"]) != record["count"]:
            raise ValueError(f"Compatibility count changed: {name}")
        for key, site in document["api_site"].items():
            if key in legacy and site != legacy[key]:
                raise ValueError(f"Conflicting legacy source: {key}")
            legacy[key] = site
    primary, identities, summary, memberships = {}, {}, {}, {}
    for group in index["groups"]:
        path = (ROOT / group["path"]).resolve()
        if path != ROOT / "subscriptions" / (group["id"] + ".json"):
            raise ValueError("Group path does not match its content type")
        text, document = read_json(path)
        if len(text.encode("utf-8")) > 2 * 1024 * 1024:
            raise ValueError("Subscription exceeds client document limit")
        if set(document) != {"cache_time", "api_site"} or document["cache_time"] != 7200:
            raise ValueError("Invalid subscription envelope")
        sites = document["api_site"]
        disabled = sum(site.get("disabled", False) for site in sites.values())
        if len(sites) != group["count"] or disabled != group["disabled_count"]:
            raise ValueError(f"Group count mismatch: {group['id']}")
        for key, site in sites.items():
            identity = source_identity(site)
            if "🔞" in site["name"] and group["id"] != "unknown":
                raise ValueError("Explicit adult sources must remain in the unknown group")
            if key in primary or identity in identities:
                raise ValueError(f"Duplicate source across primary subscriptions: {key}")
            if key in legacy and site != legacy[key]:
                raise ValueError(f"Source configuration or disabled state changed: {key}")
            primary[key], identities[identity] = site, key
            memberships[key] = group["id"]
        summary[group["name"]] = {"sources": len(sites), "disabled": disabled}
    aliases = index["aliases"]
    if len(legacy) != index["legacy_stable_keys"] or len(primary) != index["total_sources"]:
        raise ValueError("Inventory totals differ from index")
    if set(legacy) - set(primary) != set(aliases):
        raise ValueError("Legacy sources missing without an explicit alias")
    for old_key, canonical_key in aliases.items():
        if old_key in primary or canonical_key not in primary:
            raise ValueError("Invalid canonical source alias")
        old, current = legacy[old_key], primary[canonical_key]
        if source_identity(old) != source_identity(current):
            raise ValueError("Alias changes API semantics or independent detail configuration")
        if old.get("disabled", False) != current.get("disabled", False):
            raise ValueError("Alias changes disabled state")
    evidence = index["classification_evidence"]
    for field, group in [("adult_keys_in_unknown", "unknown"), ("unknown_keys", "unknown"), ("short_drama_keys", "short-drama"), ("animation_keys", "animation")]:
        if any(memberships.get(key) != group for key in evidence[field]):
            raise ValueError(f"Classification evidence does not match group: {field}")
    files = {path.name for path in (ROOT / "subscriptions").glob("*.json")}
    if files != {"index.json", *(key + ".json" for key in expected)}:
        raise ValueError("Unexpected subscription file outside the four fixed groups")
    print(json.dumps({"status": "PASSED", "sources": len(primary), "aliases": len(aliases), "groups": summary}, ensure_ascii=False))


if __name__ == "__main__":
    check()
