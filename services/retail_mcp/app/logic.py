from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib import error, parse, request

VALID_ROLES = {"associate", "merch", "support"}
MIN_QTY = 1
MAX_QTY = 20

_CANONICAL_DOC_ROOT = "https://retailnext.internal/docs"
_DOC_SLUG_OVERRIDES = {
    "Returns_and_Holds_Policy": "returns",
    "Associate_Playbook": "associate-playbook",
    "Merch_Transfer_Playbook": "merch-transfer-playbook",
    "Support_Runbook": "support-runbook",
    "Styling_Guide_Spring_2026": "styling-guide-spring-2026",
}


@dataclass(frozen=True)
class KnowledgeSection:
    section_id: str
    title: str
    url: str
    content: str


_knowledge_index: Optional[dict[str, KnowledgeSection]] = None
_known_skus: Optional[set[str]] = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def docs_dir() -> Path:
    return Path(os.getenv("RETAIL_MCP_DOCS_DIR", str(_project_root() / "docs" / "knowledge"))).resolve()


def data_dir() -> Path:
    return Path(os.getenv("RETAIL_MCP_DATA_DIR", str(_project_root() / "data"))).resolve()


def retailcore_base_url(override: Optional[str] = None) -> str:
    if override:
        return override.rstrip("/")
    return os.getenv("RETAILCORE_BASE_URL", "http://retailcore:8080").rstrip("/")


def _doc_slug(doc_stem: str) -> str:
    if doc_stem in _DOC_SLUG_OVERRIDES:
        return _DOC_SLUG_OVERRIDES[doc_stem]
    return doc_stem.lower().replace("_", "-")


def _doc_title(doc_stem: str) -> str:
    return doc_stem.replace("_", " ")


def _parse_sections(file_path: Path) -> list[KnowledgeSection]:
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    heading_indices = [idx for idx, line in enumerate(lines) if re.match(r"^\s*#{1,6}\s+\S+", line)]
    doc_stem = file_path.stem
    doc_slug = _doc_slug(doc_stem)
    results: list[KnowledgeSection] = []

    if not heading_indices:
        section_id = f"doc:{doc_stem}#section-1"
        url = f"{_CANONICAL_DOC_ROOT}/{doc_slug}#section-1"
        results.append(
            KnowledgeSection(
                section_id=section_id,
                title=_doc_title(doc_stem),
                url=url,
                content=text.strip(),
            )
        )
        return results

    for section_number, start_idx in enumerate(heading_indices, start=1):
        end_idx = heading_indices[section_number] if section_number < len(heading_indices) else len(lines)
        section_lines = lines[start_idx:end_idx]
        first_line = section_lines[0]
        heading = re.sub(r"^\s*#{1,6}\s*", "", first_line).strip()
        section_id = f"doc:{doc_stem}#section-{section_number}"
        url = f"{_CANONICAL_DOC_ROOT}/{doc_slug}#section-{section_number}"
        title = f"{_doc_title(doc_stem)}: {heading}"
        content = "\n".join(section_lines).strip()

        results.append(
            KnowledgeSection(
                section_id=section_id,
                title=title,
                url=url,
                content=content,
            )
        )
    return results


def _build_knowledge_index() -> dict[str, KnowledgeSection]:
    index: dict[str, KnowledgeSection] = {}
    knowledge_files = sorted(docs_dir().glob("*.md"))
    for file_path in knowledge_files:
        for section in _parse_sections(file_path):
            index[section.section_id] = section
    return index


def knowledge_index() -> dict[str, KnowledgeSection]:
    global _knowledge_index
    if _knowledge_index is None:
        _knowledge_index = _build_knowledge_index()
    return _knowledge_index


def _build_known_skus() -> set[str]:
    products_path = data_dir() / "products.csv"
    if not products_path.exists():
        raise ValueError(f"products.csv not found: {products_path}")
    with products_path.open("r", newline="", encoding="utf-8") as handle:
        return {row["sku"] for row in csv.DictReader(handle)}


def known_skus() -> set[str]:
    global _known_skus
    if _known_skus is None:
        _known_skus = _build_known_skus()
    return _known_skus


def _validate_role(role: str) -> str:
    normalized = role.lower().strip()
    if normalized not in VALID_ROLES:
        raise ValueError(f"Invalid role '{role}'. Expected one of: {sorted(VALID_ROLES)}")
    return normalized


def _validate_sku(sku: str) -> None:
    if sku not in known_skus():
        raise ValueError(f"Unknown SKU '{sku}'. Use a SKU from data/products.csv.")


def _validate_qty(qty: int) -> None:
    if qty < MIN_QTY or qty > MAX_QTY:
        raise ValueError(f"qty must be between {MIN_QTY} and {MAX_QTY}. Received {qty}.")


def _http_json(
    method: str,
    path: str,
    role: str,
    payload: Optional[dict[str, Any]] = None,
    params: Optional[dict[str, Any]] = None,
    base_url: Optional[str] = None,
) -> tuple[int, dict[str, Any]]:
    url = retailcore_base_url(base_url) + path
    if params:
        query = parse.urlencode(params)
        url = f"{url}?{query}"

    headers = {
        "X-DEMO-ROLE": role,
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(url=url, data=body, headers=headers, method=method)

    try:
        with request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            return int(response.status), data
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        detail = raw
        if raw:
            try:
                parsed = json.loads(raw)
                detail = parsed.get("detail", raw)
            except json.JSONDecodeError:
                detail = raw
        raise RuntimeError(f"RetailCore request failed ({method} {path}): {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"RetailCore is unreachable at {retailcore_base_url(base_url)}: {exc.reason}") from exc


def _with_status(data: dict[str, Any], status_code: int) -> dict[str, Any]:
    enriched = dict(data)
    enriched["upstream_status"] = status_code
    return enriched


def search_documents(query: str, limit: int = 5) -> dict[str, Any]:
    sections = knowledge_index().values()
    query_terms = re.findall(r"[a-z0-9]+", query.lower())
    scored: list[tuple[int, str, KnowledgeSection]] = []

    for section in sections:
        haystack = f"{section.title}\n{section.content}".lower()
        if not query_terms:
            score = 1
        else:
            score = sum(haystack.count(term) for term in query_terms)
            if query.lower() in haystack:
                score += 2
        if score > 0:
            scored.append((score, section.section_id, section))

    scored.sort(key=lambda item: (-item[0], item[1]))
    results = [
        {"id": section.section_id, "title": section.title, "url": section.url}
        for _, _, section in scored[:limit]
    ]
    return {"results": results}


def fetch_document(section_id: str) -> dict[str, Any]:
    section = knowledge_index().get(section_id)
    if section is None:
        raise ValueError(f"Unknown document id '{section_id}'.")
    return {
        "id": section.section_id,
        "title": section.title,
        "url": section.url,
        "content": section.content,
    }


def inventory_lookup_action(
    sku: str,
    store_id: str,
    radius_miles: float,
    role: str,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    normalized_role = _validate_role(role)
    _validate_sku(sku)
    if radius_miles <= 0:
        raise ValueError("radius_miles must be greater than 0.")

    status, data = _http_json(
        method="GET",
        path="/inventory/lookup",
        role=normalized_role,
        params={"sku": sku, "store_id": store_id, "radius_miles": radius_miles},
        base_url=base_url,
    )
    return _with_status(data, status)


def reserve_item_action(
    sku: str,
    store_id: str,
    qty: int,
    confirm: bool,
    role: str,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    normalized_role = _validate_role(role)
    _validate_sku(sku)
    _validate_qty(qty)

    status, data = _http_json(
        method="POST",
        path="/reserve",
        role=normalized_role,
        payload={"sku": sku, "store_id": store_id, "qty": qty, "confirm": confirm},
        base_url=base_url,
    )
    return _with_status(data, status)


def create_transfer_action(
    from_store: str,
    to_store: str,
    sku: str,
    qty: int,
    confirm: bool,
    role: str,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    normalized_role = _validate_role(role)
    if normalized_role != "merch":
        raise ValueError("create_transfer requires role=merch.")
    _validate_sku(sku)
    _validate_qty(qty)

    status, data = _http_json(
        method="POST",
        path="/transfer",
        role=normalized_role,
        payload={
            "from_store": from_store,
            "to_store": to_store,
            "sku": sku,
            "qty": qty,
            "confirm": confirm,
        },
        base_url=base_url,
    )
    return _with_status(data, status)


def create_ticket_action(
    store_id: str,
    category: str,
    severity: str,
    description: str,
    role: str,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    normalized_role = _validate_role(role)
    if not description.strip():
        raise ValueError("description must not be empty.")

    status, data = _http_json(
        method="POST",
        path="/tickets",
        role=normalized_role,
        payload={
            "store_id": store_id,
            "category": category,
            "severity": severity,
            "description": description,
        },
        base_url=base_url,
    )
    return _with_status(data, status)
