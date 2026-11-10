import hashlib
import ipaddress
import json
from collections import Counter, defaultdict
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
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith((".localhost", ".local")):
        raise ValueError("Source URL points to a local hostname")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Source URL points to a non-public address")
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


def check_directory_imports(index, primary, memberships):
    accepted = {"ADDED", "EXISTING_INTERFACE", "DUPLICATE_DIRECTORY_INTERFACE"}
    rejected = {"WITHDRAWN_BY_DIRECTORY", "NO_SUPPORTED_PUBLIC_CATALOG"}
    for batch in index.get("directory_imports", []):
        path = (ROOT / batch["audit"]).resolve()
        if path.parent != (ROOT / "audits").resolve():
            raise ValueError("Directory audit path escapes audits directory")
        _, audit = read_json(path)
        if content_hash(audit) != batch["content_sha256"]:
            raise ValueError("Directory audit fingerprint differs from index")
        entries = audit["entries"]
        if len(entries) != batch["entry_count"] or audit["directory"] != batch["directory"]:
            raise ValueError("Directory audit inventory differs from index")
        if Counter(row["status"] for row in entries) != batch["status_counts"]:
            raise ValueError("Directory audit status counts differ from index")
        ids, added = set(), set()
        for row in entries:
            source_id = row["directory_id"]
            if not source_id.isdecimal() or source_id in ids:
                raise ValueError("Duplicate or invalid directory entry")
            ids.add(source_id)
            if row["directory_page"] != audit["directory"] + source_id + ".html":
                raise ValueError("Directory entry URL differs from its identity")
            status = row["status"]
            if status in rejected:
                if "source_key" in row or not row.get("reason"):
                    raise ValueError("Rejected directory entry claims an imported identity")
                if status == "WITHDRAWN_BY_DIRECTORY" and row["interfaces"]:
                    raise ValueError("Withdrawn entry contains a fabricated interface")
                continue
            if status not in accepted or row["source_key"] not in primary:
                raise ValueError("Directory entry has no supported repository identity")
            key = row["source_key"]
            selected = source_identity({"api": row["selected_api"]})
            if selected != source_identity(primary[key]) or memberships[key] != row["group"]:
                raise ValueError("Directory mapping changes API identity or content group")
            if row["selected_api"] not in {endpoint["url"] for endpoint in row["interfaces"]}:
                raise ValueError("Selected API was not published by the directory entry")
            if status == "ADDED":
                if key in added:
                    raise ValueError("Duplicate added directory identity")
                added.add(key)
        if sorted(added) != sorted(batch["added_keys"]):
            raise ValueError("Added directory identities differ from index")


def check():
    _, index = read_json(ROOT / "subscriptions/index.json")
    expected = {"film-tv": "影视", "short-drama": "短剧", "animation": "动漫", "unknown": "未知"}
    if index.get("default_enabled") is not True:
        raise ValueError("Repository sources must be enabled by default")
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
        if disabled:
            raise ValueError("Primary subscription must not disable sources by default")
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
    check_directory_imports(index, primary, memberships)
    print(json.dumps({"status": "PASSED", "sources": len(primary), "aliases": len(aliases), "groups": summary}, ensure_ascii=False))


if __name__ == "__main__":
    check()
