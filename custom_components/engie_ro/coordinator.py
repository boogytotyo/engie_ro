from __future__ import annotations
import logging
from datetime import timedelta, datetime, timezone
from typing import Any, List, Dict
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from .const import (
    DOMAIN, CONF_BASE_URL, CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN_FILE, CONF_DEVICE_ID,
    CONF_AUTH_MODE, AUTH_MODE_MOBILE, CONF_BEARER_TOKEN,
    DEFAULT_BASE_URL, DEFAULT_TOKEN_FILE, UPDATE_INTERVAL_SEC, ATTRIBUTION
)
from .api import EngieClient, EngieHTTPError, EngieUnauthorized
from .auth import EngieAuthManager

# --- Helpers for Engie România custom formatting ---

def _fmt_money_lei(value: float | int | str | None) -> str:
    try:
        val = float(str(value).replace(",", "."))
    except Exception:
        return ""
    s = f"{val:.2f}"
    s = s.replace(".", ",")
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


_LOGGER = logging.getLogger(__name__)

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
    keys = {
        "street": ["street","strada","address_line1","adresa","address1"],
        "number": ["number","nr","numar"],
        "block": ["block","bloc","bl"],
        "apartment": ["apartment","ap","apt"],
        "city": ["city","oras","localitate"],
        "county": ["county","judet","region"],
    }
    def find(pl, names):
        for k, v in _walk(pl):
            if k in names and v not in (None,"",[],{}):
                return str(v)
        return None
    for p in payloads:
        if not p:
            continue
        street = find(p, keys["street"])
        number = find(p, keys["number"])
        block = find(p, keys["block"])
        apt = find(p, keys["apartment"])
        city = find(p, keys["city"])
        county = find(p, keys["county"])
        parts = []
        if street: parts.append(street)
        if number: parts.append(f"Nr. {number}")
        if block: parts.append(f"Bl.{block}")
        if apt: parts.append(f"Apt. {apt}")
        if city: parts.append(city)
        if county and county != city: parts.append(county)
        if parts:
            return ", ".join(parts)
    return None

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
        self.auth = EngieAuthManager(self.client, username, password, token_file, device_id, auth_mode, bearer_token)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            await self.auth.ensure_valid_token()

            me = await self.client.get_user()
            places = await self.client.get_places()

            contract_account = _find_first(places, ["contract_account","contractAccount","ca","accountNumber"])
            contract_account_number = _find_first(places, ["contract_account_number","contractAccountNumber"])
            poc_number = _find_first(places, ["poc_number","pocNumber","poc"])
            pa = _find_first(places, ["pa","partnerAccount","account_pa"])
            division = _find_first(places, ["division","divizie"]) or "gaz"

            divisions_payload = None
            try:
                if poc_number:
                    divisions_payload = await self.client.get_divisions(poc_number, pa=pa)
            except EngieUnauthorized:
                await self.auth.refresh_after_401()
                if poc_number:
                    divisions_payload = await self.client.get_divisions(poc_number, pa=pa)
            except Exception as e:
                _LOGGER.debug("Divisions fetch failed: %s", e)

            index_info = None
            installation_number = None
            try:
                if poc_number:
                    idx_payload = await self.client.get_index_window(poc_number, division=division, pa=pa, installation_number=None)
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
                                installation_number = inst.get("installation_number") or inst.get("installationNumber")
            except EngieUnauthorized:
                await self.auth.refresh_after_401()
            except Exception as e:
                _LOGGER.debug("Index window fetch failed: %s", e)

            invoices_details = None
            unpaid_list = []
            if contract_account or contract_account_number:
                ca_for_balance = contract_account_number or contract_account
                try:
                    invoices_details = await self.client.get_invoices_details(ca_for_balance)
                except EngieUnauthorized:
                    await self.auth.refresh_after_401()
                    invoices_details = await self.client.get_invoices_details(ca_for_balance)
                except Exception as e:
                    _LOGGER.debug("Invoices details fetch failed: %s", e)

            unpaid_last_value = None
            try:
                if isinstance(invoices_details, dict):
                    d = invoices_details.get("data")

                    # Calculate unpaid_total from nested invoices[].invoices[].unpaid
                    unpaid_total = 0.0
                    unpaid_items = []
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
                                        unpaid_items.append({
                                            "invoice_number": inv.get("invoice_number"),
                                            "unpaid": inv.get("unpaid"),
                                            "due_date": inv.get("due_date"),
                                            "total": inv.get("total"),
                                        })
                    except Exception as e:
                        _LOGGER.debug("Parse invoices unpaid failed: %s", e)
                    if isinstance(d, dict):
                        pending = d.get("pending") or []
                        if isinstance(pending, list):
                            unpaid_list = pending
                            for item in pending:
                                val = item.get("amount") or item.get("value") or item.get("total") or item.get("sum")
                                if val is not None:
                                    try:
                                        unpaid_last_value = float(str(val).replace(",", "."))
                                    except Exception:
                                        pass
            except Exception as e:
                _LOGGER.debug("Parse unpaid list failed: %s", e)

            
            # Fetch invoices history (last 365 days) explicitly
            inv_hist = {}
            try:
                today = datetime.now().date()
                end_date = today.strftime("%Y-%m-%d")
                start_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")
                if poc_number and pa:
                    inv_hist = await self.client.get_invoices_history(poc_number=str(poc_number), start_date=start_date, end_date=end_date, pa=str(pa))
            except EngieUnauthorized:
                await self.auth.refresh_after_401()
            except Exception as e:
                _LOGGER.debug("Invoices history fetch failed: %s", e)
            invoices_flat: List[Dict] = []
            try:
                if poc_number:
                    hist = await self.client.get_invoices_history(poc_number, division=division, pa=pa, installation_number=installation_number)
                    if isinstance(hist, dict):
                        data = hist.get("data") or []
                        if isinstance(data, list):
                            for m in data:
                                invs = m.get("invoice_numbers") or []
                                for it in invs:
                                    if isinstance(it, dict):
                                        invoices_flat.append({
                                            "month": m.get("invoiced_at"),
                                            "invoice_number": it.get("invoice_number"),
                                            "division": it.get("division"),
                                            "invoiced_at": it.get("invoiced_at"),
                                            "consum_gaz": it.get("consum_gaz"),
                                            "consum_elec": it.get("consum_elec"),
                                        })
            except EngieUnauthorized:
                await self.auth.refresh_after_401()
            except Exception as e:
                _LOGGER.debug("Invoices history fetch failed: %s", e)

            invoices_year_current: List[Dict] = []
            invoices_year_prev: List[Dict] = []
            try:
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
            except Exception as e:
                _LOGGER.debug("Year bucketing failed: %s", e)

            address = _parse_address(places, divisions_payload)
            now_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            profile = {
                "email": (me.get("data") or {}).get("email") if isinstance(me, dict) else None,
                "name": (me.get("data") or {}).get("user_name") if isinstance(me, dict) else None,
                "phone": (me.get("data") or {}).get("phone") if isinstance(me, dict) else None,
            }

            
            # --- Build 'istoric_facturi' using /v1/index/consumption/{POC} ---
            consumption_last_value = None
            consumption_lines: list[str] = []
            consumption_count = 0
            consumption_total = 0.0
            try:
                today = datetime.now().date()
                end_date = today.strftime("%Y-%m-%d")
                start_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")
                if poc_number and pa:
                    cons = await self.client.get_consumption(poc_number, start_date, end_date, pa=pa)
                    items = []
                    if isinstance(cons, dict):
                        arr = cons.get("data") or []
                        for month_item in arr:
                            invs = month_item.get("invoice_numbers") or []
                            for inv in invs:
                                d = str(inv.get("invoiced_at") or month_item.get("invoiced_at") or "")
                                amount = inv.get("consum_gaz") or inv.get("value") or inv.get("amount") or 0
                                try:
                                    amount_num = float(str(amount).replace(",", "."))
                                except Exception:
                                    amount_num = 0.0
                                items.append((d, amount_num))
                    def _parse_date(d):
                        try:
                            if len(d) == 7:
                                return datetime.strptime(d + "-01", "%Y-%m-%d")
                            return datetime.strptime(d[:10], "%Y-%m-%d")
                        except Exception:
                            return datetime.min
                    items.sort(key=lambda x: _parse_date(x[0]), reverse=True)
                    consumption_count = len(items)
                    for d, v in items:
                        consumption_total += float(v)
                        consumption_lines.append(f"{_fmt_date_ro(d)}\t{_fmt_money_lei(v)}")
                    if items:
                        consumption_last_value = _fmt_money_lei(items[0][1])
            except Exception as e:
                _LOGGER.debug("Failed to build istoric_facturi: %s", e)

            # --- Build 'istoric_index' using POST /v1/index/history ---
            index_history_list: list[str] = []
            index_history_last = None
            try:
                today = datetime.now().date()
                start_date_hist = (today - timedelta(days=3*365)).strftime("%Y-%m-%d")
                if poc_number and division and index_info:
                    autocit_val = (index_info or {}).get("autocit") or ""
                    hist = await self.client.get_index_history_post(autocit=str(autocit_val), poc_number=str(poc_number), division=str(division), start_date=start_date_hist)
                    latest_date = None
                    latest_index = None
                    this_year = today.year
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
                            if dt and (latest_date is None or dt > latest_date):
                                latest_date = dt
                                latest_index = idx_num
                            if dt and dt.year == this_year:
                                if idx_num is not None:
                                    index_history_list.append(f"{dt.strftime('%d.%m.%Y')}\t{idx_num}")
                    if latest_index is not None:
                        index_history_last = latest_index
            except Exception as e:
                _LOGGER.debug("Failed to build istoric_index: %s", e)

            return {
                "profile": profile,
                "address": address,
                "me": me,
                "places": places,
                "contract_account": contract_account,
                "contract_account_number": contract_account_number or contract_account,
                "poc_number": poc_number,
                "division": division,
                "pa": pa,
                "installation_number": installation_number,
                "unpaid_list": unpaid_list,
                "unpaid_last_value": unpaid_last_value,
                "invoices_details": invoices_details,
                "invoices_history": inv_hist,
                "unpaid_total": unpaid_total,
                "unpaid_items": unpaid_items,
                "invoices_flat": invoices_flat,
                "invoices_year_current": invoices_year_current,
                "invoices_year_prev": invoices_year_prev,
                "index_info": index_info,
                "consumption_last_value": consumption_last_value,
                "consumption_lines": consumption_lines,
                "consumption_count": consumption_count,
                "consumption_total": round(consumption_total, 2),
                "index_history_last": index_history_last,
                "index_history_list": index_history_list,
    
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
