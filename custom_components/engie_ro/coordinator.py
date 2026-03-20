from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EngieClient, EngieHTTPError, EngieUnauthorized
from .auth import EngieAuthManager
from .const import (
    ATTRIBUTION,
    AUTH_MODE_MOBILE,
    CONF_AUTH_MODE,
    CONF_BASE_URL,
    CONF_BEARER_TOKEN,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_TOKEN_FILE,
    CONF_USERNAME,
    DEFAULT_BASE_URL,
    DEFAULT_TOKEN_FILE,
    UPDATE_INTERVAL_SEC,
)

_LOGGER = logging.getLogger(__name__)

_RO_MONTHS = [
    "",
    "ianuarie",
    "februarie",
    "martie",
    "aprilie",
    "mai",
    "iunie",
    "iulie",
    "august",
    "septembrie",
    "octombrie",
    "noiembrie",
    "decembrie",
]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_money_lei(value: float | int | str | None) -> str:
    try:
        val = float(str(value).replace(",", "."))
    except Exception:
        return ""
    s = f"{val:.2f}".replace(".", ",")
    return f"{s} lei"


def _fmt_date_ro(iso_date: str) -> str:
    try:
        if len(iso_date) == 7:
            dt = datetime.strptime(iso_date + "-01", "%Y-%m-%d")
        else:
            dt = datetime.strptime(iso_date[:10], "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return iso_date


# ---------------------------------------------------------------------------
# Walking / extraction helpers
# ---------------------------------------------------------------------------


def _walk(d):
    if isinstance(d, dict):
        for k, v in d.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(d, list):
        for it in d:
            yield from _walk(it)


def _find_first(payload: Any, keys: list[str]):
    for k, v in _walk(payload):
        if k in keys and v not in (None, "", [], {}):
            return str(v)
    return None


def _parse_address(*payloads: Any):
    def find(pl, names):
        for k, v in _walk(pl):
            if k in names and v not in (None, "", [], {}):
                return str(v)
        return None

    street_keys = ["street", "strada", "address_line1", "adresa", "address1"]
    number_keys = ["number", "nr", "numar"]
    block_keys = ["block", "bloc", "bl"]
    apt_keys = ["apartment", "ap", "apt"]
    city_keys = ["city", "oras", "localitate"]
    county_keys = ["county", "judet", "region"]

    for p in payloads:
        if not p:
            continue
        street = find(p, street_keys)
        number = find(p, number_keys)
        block = find(p, block_keys)
        apt = find(p, apt_keys)
        city = find(p, city_keys)
        county = find(p, county_keys)
        parts = []
        if street:
            parts.append(street)
        if number:
            parts.append(f"Nr. {number}")
        if block:
            parts.append(f"Bl.{block}")
        if apt:
            parts.append(f"Apt. {apt}")
        if city:
            parts.append(city)
        if county and county != city:
            parts.append(county)
        if parts:
            return ", ".join(parts)
    return None


def _extract_places_from_raw(places_raw: Any) -> list[dict]:
    """Return all distinct consumption places (keyed by poc_number)."""

    def _walk_nodes(node: Any):
        if isinstance(node, dict):
            yield node
            for value in node.values():
                yield from _walk_nodes(value)
        elif isinstance(node, list):
            for item in node:
                yield from _walk_nodes(item)

    places: list[dict] = []
    seen: set[str] = set()
    for item in _walk_nodes(places_raw):
        if not isinstance(item, dict):
            continue
        poc = item.get("poc_number") or item.get("pocNumber") or item.get("poc")
        if not poc:
            continue
        uid = str(poc).strip()
        if not uid or uid in seen:
            continue
        seen.add(uid)
        places.append(item)
    return places


# ---------------------------------------------------------------------------
# Per-place data fetcher
# ---------------------------------------------------------------------------


async def _fetch_place_data(
    client: EngieClient,
    auth: Any,
    place: dict,
) -> dict[str, Any]:
    """Fetch all 7-sensor data for a single consumption place."""

    poc_number = _find_first(place, ["poc_number", "pocNumber", "poc"])
    contract_account = _find_first(
        place, ["contract_account", "contractAccount", "ca", "accountNumber"]
    )
    contract_account_number = _find_first(
        place, ["contract_account_number", "contractAccountNumber"]
    )
    pa = _find_first(place, ["pa", "partnerAccount", "account_pa"])
    division = _find_first(place, ["division", "divizie"]) or "gaz"

    result: dict[str, Any] = {
        "poc_number": poc_number,
        "contract_account": contract_account,
        "contract_account_number": contract_account_number or contract_account,
        "pa": pa,
        "division": division,
        "address": None,
        "index_info": None,
        "installation_number": None,
        "invoices_details": None,
        "unpaid_list": [],
        "unpaid_last_value": None,
        "unpaid_total": 0.0,
        "unpaid_items": [],
        "inv_hist": {},
        "invoices_flat": [],
        "invoices_year_current": [],
        "invoices_year_prev": [],
        "consumption_by_month": {},
        "consumption_count": 0,
        "consumption_total": 0.0,
        "index_history_last": None,
        "index_history_by_month": {},
    }

    if not poc_number:
        return result

    # --- Divisions / address ---
    divisions_payload = None
    try:
        divisions_payload = await client.get_divisions(poc_number, pa=pa)
    except EngieUnauthorized:
        await auth.refresh_after_401()
        try:
            divisions_payload = await client.get_divisions(poc_number, pa=pa)
        except Exception as e:
            _LOGGER.debug("Divisions fetch failed for %s: %s", poc_number, e)
    except Exception as e:
        _LOGGER.debug("Divisions fetch failed for %s: %s", poc_number, e)

    result["address"] = _parse_address(place, divisions_payload)

    # --- Index window ---
    index_info = None
    installation_number = None
    try:
        idx_payload = await client.get_index_window(
            poc_number, division=division, pa=pa, installation_number=None
        )
        if isinstance(idx_payload, dict):
            data_list = idx_payload.get("data") or []
            if isinstance(data_list, list) and data_list:
                insts = data_list[0].get("installations") or []
                if insts:
                    inst = insts[0]
                    dates = inst.get("next_read_dates") or {}
                    index_info = {
                        "last_index": inst.get("last_index"),
                        "autocit": inst.get("autocit"),
                        "permite_index": inst.get("permite_index"),
                        "start_date": dates.get("startDate"),
                        "end_date": dates.get("endDate"),
                    }
                    installation_number = inst.get("installation_number") or inst.get(
                        "installationNumber"
                    )
    except EngieUnauthorized:
        await auth.refresh_after_401()
    except Exception as e:
        _LOGGER.debug("Index window fetch failed for %s: %s", poc_number, e)

    result["index_info"] = index_info
    result["installation_number"] = installation_number

    # --- Invoices details (unpaid) ---
    invoices_details = None
    unpaid_list: list = []
    ca_for_balance = contract_account_number or contract_account
    if ca_for_balance:
        try:
            invoices_details = await client.get_invoices_details(ca_for_balance)
        except EngieUnauthorized:
            await auth.refresh_after_401()
            try:
                invoices_details = await client.get_invoices_details(ca_for_balance)
            except Exception as e:
                _LOGGER.debug("Invoices details fetch failed for %s: %s", poc_number, e)
        except Exception as e:
            _LOGGER.debug("Invoices details fetch failed for %s: %s", poc_number, e)

    unpaid_last_value = None
    unpaid_total = 0.0
    unpaid_items: list = []
    try:
        if isinstance(invoices_details, dict):
            d = invoices_details.get("data")
            try:
                invs = d.get("invoices") if isinstance(d, dict) else None
                if isinstance(invs, list):
                    for acc in invs:
                        inv_list = (acc or {}).get("invoices") or []
                        for inv in inv_list:
                            upv = inv.get("unpaid")
                            try:
                                upf = float(str(upv).replace(",", ".")) if upv is not None else 0.0
                            except Exception:
                                upf = 0.0
                            if upf > 0:
                                unpaid_total += upf
                                unpaid_items.append(
                                    {
                                        "invoice_number": inv.get("invoice_number"),
                                        "unpaid": inv.get("unpaid"),
                                        "due_date": inv.get("due_date"),
                                        "total": inv.get("total"),
                                    }
                                )
            except Exception as e:
                _LOGGER.debug("Parse invoices unpaid failed for %s: %s", poc_number, e)
            if isinstance(d, dict):
                pending = d.get("pending") or []
                if isinstance(pending, list):
                    unpaid_list = pending
                    for item in pending:
                        val = (
                            item.get("amount")
                            or item.get("value")
                            or item.get("total")
                            or item.get("sum")
                        )
                        if val is not None:
                            try:
                                unpaid_last_value = float(str(val).replace(",", "."))
                            except Exception:
                                pass
    except Exception as e:
        _LOGGER.debug("Parse unpaid list failed for %s: %s", poc_number, e)

    result["invoices_details"] = invoices_details
    result["unpaid_list"] = unpaid_list
    result["unpaid_last_value"] = unpaid_last_value
    result["unpaid_total"] = unpaid_total
    result["unpaid_items"] = unpaid_items

    # --- Dates for history queries ---
    today = datetime.now().date()
    end_date = today.strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")

    # --- Invoices history (arhivă facturi) ---
    inv_hist: dict = {}
    if pa:
        try:
            inv_hist = await client.get_invoices_history(
                poc_number=str(poc_number),
                start_date=start_date,
                end_date=end_date,
                pa=str(pa),
            )
        except EngieUnauthorized:
            await auth.refresh_after_401()
        except Exception as e:
            _LOGGER.debug("Invoices history fetch failed for %s: %s", poc_number, e)

    result["inv_hist"] = inv_hist

    # --- Invoices flat (for year buckets) ---
    invoices_flat: list[dict] = []
    try:
        if isinstance(inv_hist, dict):
            data = inv_hist.get("data") or []
            if isinstance(data, list):
                for m in data:
                    invs2 = m.get("invoice_numbers") or []
                    for it in invs2:
                        if isinstance(it, dict):
                            invoices_flat.append(
                                {
                                    "month": m.get("invoiced_at"),
                                    "invoice_number": it.get("invoice_number"),
                                    "division": it.get("division"),
                                    "invoiced_at": it.get("invoiced_at"),
                                    "consum_gaz": it.get("consum_gaz"),
                                    "consum_elec": it.get("consum_elec"),
                                }
                            )
    except Exception as e:
        _LOGGER.debug("Invoices flat parse failed for %s: %s", poc_number, e)

    invoices_year_current: list[dict] = []
    invoices_year_prev: list[dict] = []
    now_year = datetime.now().year
    for it in invoices_flat:
        m = (it.get("month") or "")[:7]
        y = int(m.split("-")[0]) if "-" in m else None
        if y == now_year:
            invoices_year_current.append(it)
        elif y == now_year - 1:
            invoices_year_prev.append(it)
    invoices_year_current.sort(key=lambda x: str(x.get("month")))
    invoices_year_prev.sort(key=lambda x: str(x.get("month")))

    result["invoices_flat"] = invoices_flat
    result["invoices_year_current"] = invoices_year_current
    result["invoices_year_prev"] = invoices_year_prev

    # --- Consumption (pentru sensor Arhivă facturi) ---
    # Produce a clean dict: { "ianuarie 2025": "370,93 lei", ... } sorted newest-first
    consumption_by_month: dict[str, str] = {}
    consumption_count = 0
    consumption_total = 0.0
    if pa:
        try:
            cons = await client.get_consumption(poc_number, start_date, end_date, pa=pa)
            items: list[tuple[str, float]] = []
            if isinstance(cons, dict):
                arr = cons.get("data") or []
                for month_item in arr:
                    invs3 = month_item.get("invoice_numbers") or []
                    for inv in invs3:
                        d = str(inv.get("invoiced_at") or month_item.get("invoiced_at") or "")
                        amount = inv.get("consum_gaz") or inv.get("value") or inv.get("amount") or 0
                        try:
                            amount_num = float(str(amount).replace(",", "."))
                        except Exception:
                            amount_num = 0.0
                        items.append((d, amount_num))

            def _parse_date(d: str) -> datetime:
                try:
                    if len(d) == 7:
                        return datetime.strptime(d + "-01", "%Y-%m-%d")
                    return datetime.strptime(d[:10], "%Y-%m-%d")
                except Exception:
                    return datetime.min

            items.sort(key=lambda x: _parse_date(x[0]), reverse=True)
            consumption_count = len(items)
            for d, v in items:
                consumption_total += v
                dt = _parse_date(d)
                if dt != datetime.min:
                    label = f"{_RO_MONTHS[dt.month]} {dt.year}"
                else:
                    label = _fmt_date_ro(d)
                consumption_by_month[label] = _fmt_money_lei(v)
        except Exception as e:
            _LOGGER.debug("Failed to build consumption for %s: %s", poc_number, e)

    result["consumption_by_month"] = consumption_by_month
    result["consumption_count"] = consumption_count
    result["consumption_total"] = round(consumption_total, 2)

    # --- Index history (Ultimul index din istoric) ---
    # Produce clean dict: { "martie 2026": 437, "februarie 2026": 340, ... } newest first
    index_history_by_month: dict[str, int] = {}
    index_history_last = None
    if index_info:
        try:
            start_date_hist = (today - timedelta(days=3 * 365)).strftime("%Y-%m-%d")
            autocit_val = (index_info or {}).get("autocit") or ""
            hist = await client.get_index_history_post(
                autocit=str(autocit_val),
                poc_number=str(poc_number),
                division=str(division),
                start_date=start_date_hist,
            )
            latest_date = None
            latest_index = None
            entries: list[tuple] = []
            if isinstance(hist, dict):
                d = hist.get("data") or {}
                arr = d.get("istoric_citiri") or []
                for it in arr:
                    date_str = str(it.get("data") or "")
                    idx_val = it.get("index")
                    try:
                        idx_num = int(str(idx_val))
                    except Exception:
                        try:
                            idx_num = int(float(str(idx_val).replace(",", ".")))
                        except Exception:
                            idx_num = None
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                    except Exception:
                        dt = None
                    if dt and idx_num is not None:
                        entries.append((dt, idx_num))
                        if latest_date is None or dt > latest_date:
                            latest_date = dt
                            latest_index = idx_num
            entries.sort(key=lambda x: x[0], reverse=True)
            for dt, idx_num in entries:
                label = f"{_RO_MONTHS[dt.month]} {dt.year}"
                if label not in index_history_by_month:
                    index_history_by_month[label] = idx_num
            if latest_index is not None:
                index_history_last = latest_index
        except Exception as e:
            _LOGGER.debug("Failed to build index history for %s: %s", poc_number, e)

    result["index_history_last"] = index_history_last
    result["index_history_by_month"] = index_history_by_month

    return result


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class EngieDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name="Engie România",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SEC),
        )
        self.entry = entry
        base_url = entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)
        token_file = entry.data.get(CONF_TOKEN_FILE, DEFAULT_TOKEN_FILE)
        device_id = entry.data.get(CONF_DEVICE_ID) or "ha-device"
        auth_mode = entry.data.get(CONF_AUTH_MODE) or AUTH_MODE_MOBILE
        bearer_token = entry.data.get(CONF_BEARER_TOKEN)

        self.client = EngieClient(base_url=base_url)
        self.auth = EngieAuthManager(
            self.client, username, password, token_file, device_id, auth_mode, bearer_token
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            await self.auth.ensure_valid_token()

            me = await self.client.get_user()
            places_raw = await self.client.get_places()

            profile = {
                "email": (me.get("data") or {}).get("email") if isinstance(me, dict) else None,
                "name": (me.get("data") or {}).get("user_name") if isinstance(me, dict) else None,
                "phone": (me.get("data") or {}).get("phone") if isinstance(me, dict) else None,
            }

            now_iso = datetime.now(UTC).astimezone().isoformat(timespec="seconds")

            # Extract all places with poc_number
            places_list = _extract_places_from_raw(places_raw)

            # Fetch full data for every place
            places_data: dict[str, dict] = {}
            for place in places_list:
                poc = _find_first(place, ["poc_number", "pocNumber", "poc"])
                if not poc:
                    continue
                try:
                    place_result = await _fetch_place_data(self.client, self.auth, place)
                    places_data[poc] = place_result
                except Exception as e:
                    _LOGGER.warning("Failed to fetch data for place %s: %s", poc, e)
                    places_data[poc] = {"poc_number": poc}

            # Backward-compatible top-level keys = first place's data
            first: dict[str, Any] = {}
            if places_data:
                first = next(iter(places_data.values()))

            return {
                "profile": profile,
                "me": me,
                "places": places_raw,
                # NEW: per-place data, keyed by poc_number
                "places_data": places_data,
                # Backward-compat (first place)
                "address": first.get("address"),
                "contract_account": first.get("contract_account"),
                "contract_account_number": first.get("contract_account_number"),
                "poc_number": first.get("poc_number"),
                "division": first.get("division"),
                "pa": first.get("pa"),
                "installation_number": first.get("installation_number"),
                "unpaid_list": first.get("unpaid_list", []),
                "unpaid_last_value": first.get("unpaid_last_value"),
                "invoices_details": first.get("invoices_details"),
                "invoices_history": first.get("inv_hist", {}),
                "unpaid_total": first.get("unpaid_total", 0.0),
                "unpaid_items": first.get("unpaid_items", []),
                "invoices_flat": first.get("invoices_flat", []),
                "invoices_year_current": first.get("invoices_year_current", []),
                "invoices_year_prev": first.get("invoices_year_prev", []),
                "index_info": first.get("index_info"),
                "consumption_by_month": first.get("consumption_by_month", {}),
                "consumption_count": first.get("consumption_count", 0),
                "consumption_total": first.get("consumption_total", 0.0),
                "index_history_last": first.get("index_history_last"),
                "index_history_by_month": first.get("index_history_by_month", {}),
                "last_update": now_iso,
                "attribution": ATTRIBUTION,
            }
        except EngieUnauthorized as e:
            raise ConfigEntryAuthFailed(str(e)) from e
        except EngieHTTPError as e:
            raise UpdateFailed(str(e)) from e
        except Exception as e:
            raise UpdateFailed(str(e)) from e

    async def async_close(self):
        await self.client.close()
