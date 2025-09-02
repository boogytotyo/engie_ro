from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTRIBUTION, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities(
        [
            EngieArhivaFacturi(coordinator, entry),
            EngieIstoricIndex(coordinator, entry),
            EngieIndexCurent(coordinator, entry),
            EngieDateUtilizatorContract(coordinator, entry),
            EngieFacturaRestantaValoare(coordinator, entry),
        ],
        True,
    )


class _BaseEngieSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


# 1) Arhivă facturi
class EngieArhivaFacturi(_BaseEngieSensor):
    _attr_name = "Engie – Arhivă facturi"
    _attr_icon = "mdi:cash-register"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self.entity_id = "sensor.engie_arhiva_facturi"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_arhiva_facturi"

    @property
    def native_value(self) -> Any:
        inv = self.coordinator.data.get("invoices") or {}
        invoices = inv.get("Invoices") or []
        if not invoices:
            return None
        # presupunem că e sortată descendent sau luăm maximum după dată
        last = invoices[0]
        return last.get("amount")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        inv = self.coordinator.data.get("invoices") or {}
        items = inv.get("Invoices") or []

        months: list[tuple[str, float]] = []
        for it in items:
            d = it.get("date") or it.get("InvoiceDate") or it.get("DateIn")
            a = it.get("amount")
            if not d or a is None:
                continue
            label = _format_month_label(d)
            months.append((label, float(a)))

        attrs: dict[str, Any] = {}
        total = 0.0
        for label, amount in months[:12]:
            total += amount
            attrs[f"{label}"] = f"{_fmt(amount)} lei"

        attrs["──────────"] = ""
        attrs["Plăți efectuate"] = len(months[:12])
        attrs["Total suma achitată"] = f"{_fmt(total)} lei"
        attrs["icon"] = "mdi:cash-register"
        attrs["friendly_name"] = "Engie – Arhivă facturi"
        attrs["attribution"] = ATTRIBUTION
        return attrs


# 2) Istoric index
class EngieIstoricIndex(_BaseEngieSensor):
    _attr_name = "Engie – Istoric index"
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self.entity_id = "sensor.engie_istoric_index"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_istoric_index"

    @property
    def native_value(self) -> Any:
        hist = self.coordinator.data.get("index_history") or {}
        items = hist.get("History") or []
        if not items:
            return None
        # cel mai recent index
        last = items[0]
        return last.get("index")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        hist = self.coordinator.data.get("index_history") or {}
        items = hist.get("History") or []

        attrs: dict[str, Any] = {}
        for it in items[:12]:
            start = it.get("start")
            end = it.get("end")
            index = it.get("index")
            if not end or index is None:
                continue
            label = _format_month_label(end)
            attrs[f"{label}"] = index

        attrs["icon"] = "mdi:counter"
        attrs["friendly_name"] = "Engie – Istoric index"
        attrs["attribution"] = ATTRIBUTION
        return attrs


# 3) Index curent (fereastră raportare)
class EngieIndexCurent(_BaseEngieSensor):
    _attr_name = "Engie – Index curent"
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self.entity_id = "sensor.engie_index_curent"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_index_curent"

    @property
    def native_value(self) -> Any:
        wnd = self.coordinator.data.get("index_window") or {}
        return "Da" if wnd.get("in_window") else "Nu"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        wnd = self.coordinator.data.get("index_window") or {}
        attrs = {
            "autocit": bool(wnd.get("in_window")),
            "permite_index": bool(wnd.get("allow_submit")),
            "interval_citire": _interval_label(wnd.get("start"), wnd.get("end")),
            "last_index": wnd.get("last_index"),
            "icon": "mdi:counter",
            "friendly_name": "Engie – Index curent",
            "attribution": ATTRIBUTION,
        }
        return attrs


# 4) Date utilizator/contract
class EngieDateUtilizatorContract(_BaseEngieSensor):
    _attr_name = "Engie – Date utilizator/contract"
    _attr_icon = "mdi:account"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self.entity_id = "sensor.engie_date_utilizator_contract"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_date_utilizator"

    @property
    def native_value(self) -> Any:
        u = self.coordinator.data.get("user_details") or {}
        # PA/POC/contract accounting – afișăm un identificator scurt
        return u.get("PA") or u.get("poc_number") or u.get("contract") or "—"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        u = self.coordinator.data.get("user_details") or {}
        attrs = {
            "email": u.get("email"),
            "nume": u.get("name") or u.get("nume"),
            "telefon": u.get("phone") or u.get("telefon"),
            "adresa": u.get("address"),
            "poc_number": u.get("poc_number"),
            "division": u.get("division"),
            "installation_number": u.get("installation_number"),
            "CONTRACT_ACCOUNT": u.get("CONTRACT_ACCOUNT"),
            "PA": u.get("PA"),
            "last_update": u.get("last_update"),
            "icon": "mdi:account",
            "friendly_name": "Engie – Date utilizator/contract",
            "attribution": ATTRIBUTION,
        }
        return attrs


# 5) Valoare factură restantă
class EngieFacturaRestantaValoare(_BaseEngieSensor):
    _attr_name = "Engie – Valoare factură restantă"
    _attr_icon = "mdi:file-document-alert"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self.entity_id = "sensor.engie_factura_restanta_valoare"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_restanta"

    @property
    def native_value(self) -> Any:
        unpaid = self.coordinator.data.get("unpaid") or {}
        items = unpaid.get("Invoices") or []
        if not items:
            return 0
        last = items[0]
        return last.get("amount", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        unpaid = self.coordinator.data.get("unpaid") or {}
        items = unpaid.get("Invoices") or []

        attrs: dict[str, Any] = {}
        total = 0.0
        if not items:
            attrs["Fara restante"] = ""
        else:
            for it in items:
                a = it.get("amount")
                d = it.get("date")
                if a is None:
                    continue
                total += float(a)
                label = _format_month_label(d) if d else "Factură"
                attrs[label] = f"{_fmt(a)} lei"

        attrs["──────────"] = ""
        attrs["Plăți restante"] = len(items)
        attrs["Total suma neachitată"] = f"{_fmt(total)} lei"
        attrs["icon"] = "mdi:file-document-alert"
        attrs["friendly_name"] = "Engie – Valoare factură restantă"
        attrs["attribution"] = ATTRIBUTION
        return attrs


# ————— Helpers —————

def _fmt(x: float | int) -> str:
    try:
        return f"{float(x):.2f}".replace(".", ",")
    except Exception:
        return "0,00"


def _format_month_label(date_str: str | None) -> str:
    if not date_str or len(date_str) < 7:
        return "—"
    # acceptă "YYYY-MM" sau "YYYY-MM-DD"
    y = int(date_str[0:4])
    m = int(date_str[5:7])
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
    nume = luni[m - 1] if 1 <= m <= 12 else str(m)
    return f"{nume}"


def _interval_label(start: str | None, end: str | None) -> str:
    s = start[0:10] if start else "—"
    e = end[0:10] if end else "—"
    return f"{s} – {e}"
