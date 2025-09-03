from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN

SENSORS = [
    "engie_date_utilizator_contract",
    "engie_factura_restanta_valoare",
    "engie_istoric_index",
    "engie_index_curent",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coord = hass.data[DOMAIN][entry.entry_id]
    entities = [EngieSensor(coord, sid) for sid in SENSORS]
    # adăugăm senzorul special pentru arhiva de facturi
    entities.append(
        EngieInvoicesSensor(
            coord, "engie_arhiva_facturi", "Engie – Arhivă facturi", "mdi:cash-register"
        )
    )
    async_add_entities(entities, True)


class EngieSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, sensor_id: str):
        super().__init__(coordinator)
        self._sid = sensor_id
        self._attr_unique_id = sensor_id

    @property
    def name(self) -> str:
        names = {
            "engie_date_utilizator_contract": "Engie – Date utilizator/contract",
            "engie_factura_restanta_valoare": "Engie – Valoare factură restantă",
            "engie_istoric_index": "Engie – Istoric index",
            "engie_index_curent": "Engie – Index curent",
        }
        return names.get(self._sid, self._sid)

    @property
    def icon(self) -> str | None:
        if self._sid in ("engie_istoric_index", "engie_index_curent"):
            return "mdi:counter"
        if self._sid == "engie_factura_restanta_valoare":
            return "mdi:file-document-alert"
        if self._sid == "engie_date_utilizator_contract":
            return "mdi:account"
        return None

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self._sid == "engie_factura_restanta_valoare":
            unpaid = data.get("unpaid_total")
            if unpaid is None:
                return 0.0
            try:
                return float(unpaid)
            except Exception:
                return unpaid
        if self._sid == "engie_index_curent":
            info = data.get("index_info") or {}
            try:
                from datetime import datetime as _dt

                today = _dt.now().date()
                sd = info.get("start_date")
                ed = info.get("end_date")
                if sd and ed:
                    sd_d = _dt.strptime(sd, "%Y-%m-%d").date()
                    ed_d = _dt.strptime(ed, "%Y-%m-%d").date()
                    return "Da" if sd_d <= today <= ed_d else "Nu"
            except Exception:
                pass
            return "Nu"
        if self._sid == "engie_istoric_index":
            # Return latest index value from history
            data = self.coordinator.data or {}
            lines = data.get("index_history_list") or []
            latest_dt = None
            latest_val = None
            from datetime import datetime as _dt

            for line in lines:
                try:
                    if "	" in line:
                        d_s, idx_s = line.split("	", 1)
                    else:
                        d_s, idx_s = line, ""
                    dt = _dt.strptime(d_s, "%d.%m.%Y")
                    if latest_dt is None or dt > latest_dt:
                        try:
                            latest_val = int(float(idx_s.replace(",", ".")))
                        except Exception:
                            latest_val = idx_s
                        latest_dt = dt
                except Exception:
                    continue
            return latest_val
        if self._sid == "engie_date_utilizator_contract":
            return (self.coordinator.data or {}).get("pa")
        return None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}

        if self._sid == "engie_date_utilizator_contract":
            prof = data.get("profile") or {}
            attrs = {
                "email": prof.get("email"),
                "nume": prof.get("name"),
                "telefon": prof.get("phone"),
                "adresa": data.get("address"),
                "poc_number": data.get("poc_number"),
                "division": data.get("division"),
                "installation_number": data.get("installation_number"),
                "contract_account": data.get("contract_account_number"),
                "pa": data.get("pa"),
                "last_update": data.get("last_update"),
            }
            return attrs

        if self._sid == "engie_factura_restanta_valoare":
            return {"unpaid_list": data.get("unpaid_list") or []}

        if self._sid == "engie_istoric_index":
            lines = data.get("index_history_list") or []
            # păstrăm ultima citire din fiecare lună
            months_map = {}
            from datetime import datetime as _dt

            for line in lines:
                try:
                    if "\t" in line:
                        d_s, idx_s = line.split("\t", 1)
                    else:
                        d_s, idx_s = line, ""
                    dt = _dt.strptime(d_s, "%d.%m.%Y")
                    month = dt.month
                    try:
                        idx_val = int(float(idx_s.replace(",", ".")))
                    except Exception:
                        idx_val = idx_s
                    if month not in months_map or dt > months_map[month][0]:
                        months_map[month] = (dt, idx_val)
                except Exception:
                    continue
            luni = [
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
            attrs = {}
            for m in sorted(months_map.keys(), reverse=True):
                attrs[luni[m - 1]] = months_map[m][1]
            attrs["attribution"] = ATTRIBUTION
            attrs["icon"] = "mdi:counter"
            attrs["friendly_name"] = "Engie – Istoric index"
            return attrs

        if self._sid == "engie_index_curent":
            idx = data.get("index_info") or {}
            attrs = {
                "autocit": idx.get("autocit"),
                "start_citire": idx.get("start_date"),
                "end_citire": idx.get("end_date"),
                "icon": "mdi:counter",
                "friendly_name": "Engie – Index curent",
            }
            return attrs

        return {}


class EngieInvoicesSensor(CoordinatorEntity, SensorEntity):
    """Arhivă facturi – folosește coordinator.data['invoices_history'] (endpoint invoices/history-only)."""

    _attr_icon = "mdi:cash-register"

    def __init__(self, coordinator, sensor_id: str, name: str, icon: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = sensor_id
        self._attr_name = name
        self._attr_icon = icon

    def _collect_invoices(self):
        """Returnează o listă [{date:'YYYY-MM-DD', amount:float}] sortată desc."""
        hist = (self.coordinator.data or {}).get("invoices_history") or {}
        months = []
        if isinstance(hist, dict):
            data = hist.get("data")
            if isinstance(data, list):
                months = data
            elif isinstance(data, dict):
                for k in ("history", "months", "items", "list", "data"):
                    v = data.get(k)
                    if isinstance(v, list):
                        months = v
                        break
        elif isinstance(hist, list):
            months = hist

        def get_date(obj):
            for k in ("invoiced_at", "issued_at", "issue_date", "date", "data", "month"):
                v = obj.get(k)
                if isinstance(v, str) and len(v) >= 7:
                    return v[:10]
            return None

        def get_amount(obj):
            for k in ("total", "amount", "value"):
                if k in obj and obj[k] is not None:
                    try:
                        return float(str(obj[k]).replace(",", "."))
                    except Exception:
                        pass
            return None

        items = []
        for m in months:
            invs = m.get("invoices") or m.get("invoice_list") or m.get("items")
            if isinstance(invs, list) and invs:
                for inv in invs:
                    d = get_date(inv) or get_date(m)
                    a = get_amount(inv)
                    if d and a is not None:
                        items.append({"date": d[:10], "amount": a})
            elif isinstance(m, dict):
                d = get_date(m)
                a = get_amount(m)
                if d and a is not None:
                    items.append({"date": d[:10], "amount": a})

        from datetime import datetime as _dt

        items.sort(
            key=lambda x: (_dt.strptime(x["date"][:10], "%Y-%m-%d") if x.get("date") else _dt.min),
            reverse=True,
        )
        return items

    @property
    def native_value(self):
        items = self._collect_invoices()
        if not items:
            return None
        return float(f"{items[0]['amount']:.2f}")

    @property
    def extra_state_attributes(self):
        attrs = {}
        items = self._collect_invoices()
        if not items:
            return attrs

        # Agregare pe lună, ultimele 12 luni
        by_month = {}
        for it in items[:240]:
            try:
                y = int(it["date"][0:4])
                m = int(it["date"][5:7])
            except Exception:
                continue
            by_month[(y, m)] = by_month.get((y, m), 0.0) + it["amount"]

        keys = sorted(by_month.keys(), key=lambda t: (t[0], t[1]), reverse=True)[:12]
        luni = [
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

        def fmt(x):
            return f"{x:.2f}".replace(".", ",") + " lei"

        total = 0.0
        for y, m in keys:
            val = by_month[(y, m)]
            attrs[luni[m - 1]] = fmt(val)
            total += val

        attrs["──────────"] = ""
        # numărul de facturi efective în lunile selectate
        sel = set(keys)
        cnt = 0
        for it in items:
            try:
                k = (int(it["date"][0:4]), int(it["date"][5:7]))
                if k in sel:
                    cnt += 1
            except Exception:
                pass
        attrs["Plăți efectuate"] = str(cnt)
        attrs["Total suma achitată"] = fmt(total)
        attrs["attribution"] = ATTRIBUTION
        return attrs
