from __future__ import annotations

from typing import Any


def _first(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def normalize_overview(raw: dict[str, Any]) -> dict[str, Any]:
    account = _first(
        raw.get("contract_account"),
        raw.get("pa"),
        raw.get("ContractAccount"),
    )
    poc = _first(
        raw.get("poc_number"),
        raw.get("POC"),
        raw.get("poc"),
        raw.get("ConsumptionPointCode"),
    )
    division = _first(
        raw.get("division"),
        raw.get("Division"),
        raw.get("energietyp"),
        "gaz",
    )
    customer = {
        "name": _first(
            raw.get("customer_name"),
            raw.get("nume"),
            raw.get("CustomerName"),
        ),
        "email": _first(
            raw.get("customer_email"),
            raw.get("email"),
            raw.get("CustomerEmail"),
        ),
    }
    return {"pa": account, "poc": poc, "division": division, "customer": customer}


def normalize_billing_history(raw: dict[str, Any]) -> dict[str, Any]:
    items = _first(raw.get("items"), raw.get("data"), [])
    norm_items = []
    for it in items or []:
        norm_items.append(
            {
                "id": _first(it.get("id"), it.get("invoice_id"), it.get("number")),
                "issue_date": _first(it.get("issue_date"), it.get("date"), it.get("InvoiceDate")),
                "due_date": _first(it.get("due_date"), it.get("DueDate")),
                "amount": float(_first(it.get("amount"), it.get("value"), it.get("sum"), 0) or 0),
                "currency": _first(it.get("currency"), it.get("Currency"), "RON"),
                "status": (_first(it.get("status"), it.get("Status")) or "").lower() or None,
                "pdf_url": _first(it.get("pdf_url"), it.get("url_pdf"), it.get("link")),
            }
        )
    last = None
    if norm_items:
        last = sorted(
            [i for i in norm_items if i.get("issue_date")],
            key=lambda x: x.get("issue_date"),
        )[-1]
    return {"items": norm_items, "last": last}


def normalize_current_index(raw: dict[str, Any]) -> dict[str, Any]:
    value = _first(raw.get("value"), raw.get("index"), raw.get("reading"))
    unit = _first(raw.get("unit"), raw.get("Unit"))
    timestamp = _first(raw.get("timestamp"), raw.get("time"), raw.get("date"))
    try:
        value = float(value) if value is not None else None
    except Exception:
        value = None
    return {"value": value, "unit": unit, "timestamp": timestamp}
