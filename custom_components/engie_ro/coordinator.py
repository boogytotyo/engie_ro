from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def find(d: dict[str, Any], key: str) -> str | None:
    return d.get(key)


class EngieCoordinator:
    def __init__(self):
        pass

    def format_address(self, p: dict[str, Any], keys: dict[str, str]) -> str | None:
        street = find(p, keys["street"])
        number = find(p, keys["number"])
        block = find(p, keys["block"])
        apt = find(p, keys["apt"])
        city = find(p, keys["city"])
        county = find(p, keys["county"])

        parts: list[str] = []
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
