from __future__ import annotations

from custom_components.engie_ro.mapping import (
    normalize_billing_history,
    normalize_current_index,
    normalize_overview,
)


def test_normalize_overview_variants():
    raw = {
        "ContractAccount": "1234567890",
        "POC": "5001888606",
        "Division": "gaz",
        "CustomerEmail": "x@y.z",
        "CustomerName": "John Doe",
    }
    out = normalize_overview(raw)
    assert out["pa"] == "1234567890"
    assert out["poc"] == "5001888606"
    assert out["division"] == "gaz"
    assert out["customer"]["email"] == "x@y.z"


def test_normalize_billing_history_list_and_last():
    raw = {
        "data": [
            {"invoice_id": "A1", "InvoiceDate": "2025-05-01", "DueDate": "2025-05-20", "value": "101.5", "Currency": "RON", "Status": "UNPAID", "url_pdf": "http://pdf/1"},
            {"invoice_id": "A2", "InvoiceDate": "2025-06-01", "DueDate": "2025-06-20", "value": 99.99, "Currency": "RON", "Status": "PAID", "url_pdf": "http://pdf/2"},
        ]
    }
    out = normalize_billing_history(raw)
    assert len(out["items"]) == 2
    assert out["last"]["id"] == "A2"
    assert out["last"]["amount"] == 99.99


def test_normalize_current_index_variants():
    raw = {"reading": "345.7", "Unit": "kWh", "time": "2025-09-01T10:00:00"}
    out = normalize_current_index(raw)
    assert out["value"] == 345.7
    assert out["unit"] == "kWh"
