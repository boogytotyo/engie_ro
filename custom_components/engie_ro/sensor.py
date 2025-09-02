from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities(
        [
            EngieFacturaSensor(coordinator, entry),
            EngieConsumSensor(coordinator, entry),
            EngieUpdateSensor(coordinator, entry),
        ],
        True,
    )


class BaseEngieSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        self.coordinator = coordinator
        self._entry = entry

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_update(self):
        await self.coordinator.async_request_refresh()

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


class EngieFacturaSensor(BaseEngieSensor):
    _attr_icon = "mdi:file-document"
    _attr_name = "Engie – Facturi"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self.entity_id = "sensor.engie_facturi"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_facturi"

    @property
    def native_value(self):
        facturi = self.coordinator.data.get("facturi") or []
        if facturi:
            return facturi[0].get("amount")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        facturi = self.coordinator.data.get("facturi") or []
        attrs: dict[str, Any] = {}
        for f in facturi:
            d = f.get("date")
            a = f.get("amount")
            if d and a is not None:
                attrs[d] = f"{a} lei"
        attrs["friendly_name"] = "Engie – Facturi"
        attrs["icon"] = "mdi:file-document"
        return attrs


class EngieConsumSensor(BaseEngieSensor):
    _attr_icon = "mdi:counter"
    _attr_name = "Engie – Consum"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self.entity_id = "sensor.engie_consum"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_consum"

    @property
    def native_value(self):
        consum = self.coordinator.data.get("consum") or []
        if consum:
            return consum[0].get("index")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = self.coordinator.data.get("consum") or []
        out: list[dict[str, Any]] = []
        for m in items:
            if isinstance(m, dict):
                d = get_date(m)
                a = get_amount(m)
                if d and a is not None:
                    out.append({"date": d[:10], "amount": a})

        attrs: dict[str, Any] = {}
        for it in out:
            attrs[it["date"]] = f"{it['amount']} mc"

        # grupare pe luni
        by_month = group_by_month(out)
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

        def fmt(x: float) -> str:
            return f"{x:.2f}".replace(".", ",") + " lei"

        total = 0.0
        for y, m in sorted(by_month.keys(), key=lambda t: (t[0], t[1]), reverse=True)[:12]:
            values = by_month[(y, m)]
            s = sum(v["amount"] for v in values if v.get("amount"))
            total += s
            luna = luni[m - 1] if 1 <= m <= 12 else str(m)
            attrs[f"{luna} {y}"] = fmt(s)

        attrs["Total"] = fmt(total)
        attrs["friendly_name"] = "Engie – Consum"
        attrs["icon"] = "mdi:counter"
        return attrs


class EngieUpdateSensor(BaseEngieSensor):
    _attr_name = "Engie România update"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self.entity_id = "sensor.engie_ro_update"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_update"

    @property
    def native_value(self):
        return f"v{VERSION}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "auto_update": False,
            "display_precision": 0,
            "installed_version": f"v{VERSION}",
            "in_progress": False,
            "latest_version": f"v{VERSION}",
            "release_summary": None,
            "release_url": f"https://github.com/boogytotyo/engie_ro/releases/v{VERSION}",
            "skipped_version": None,
            "title": None,
            "update_percentage": None,
            "entity_picture": "https://brands.home-assistant.io/_/engie_ro/icon.png",
            "friendly_name": "Engie România update",
            "supported_features": 23,
        }


# === Helper functions ===


def get_date(m: dict[str, Any]) -> str | None:
    return m.get("date")


def get_amount(m: dict[str, Any]) -> float | None:
    return m.get("amount")


def group_by_month(items: list[dict[str, Any]]) -> dict[tuple[int, int], list[dict]]:
    by_month: dict[tuple[int, int], list[dict]] = {}
    for it in items[:240]:
        try:
            y = int(it["date"][0:4])
            m = int(it["date"][5:7])
        except Exception:
            continue
        by_month.setdefault((y, m), []).append(it)
    return by_month
