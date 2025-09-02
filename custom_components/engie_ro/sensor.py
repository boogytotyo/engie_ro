from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity

_LOGGER = logging.getLogger(__name__)


class EngieSensor(SensorEntity):
    def __init__(self):
        self._attr_name = "Engie Sensor"

    @property
    def state(self):
        return "demo"


def parse_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in items:
        if isinstance(m, dict):
            d = get_date(m)
            a = get_amount(m)
            if d and a is not None:
                out.append({"date": d[:10], "amount": a})
    return out


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


def format_amounts() -> None:
    def fmt(x: float) -> str:
        return f"{x:.2f}".replace(".", ",") + " lei"

    total = 0.0
    _LOGGER.debug("Total calculat: %s", fmt(total))
