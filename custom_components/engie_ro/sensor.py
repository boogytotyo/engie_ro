from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import EngieDataCoordinator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _in_reading_window(index_info: dict) -> str:
    """Return 'Da' if today falls within the meter-reading window, 'Nu' otherwise.

    Dates from the API are in dd-mm-yyyy format (e.g. '20-03-2026').
    Falls back to the legacy permite_index/autocit flags if dates are missing.
    """
    from datetime import date

    start_raw = index_info.get("start_date") or ""
    end_raw = index_info.get("end_date") or ""

    if start_raw and end_raw:
        try:
            start = date(
                int(start_raw[6:10]),
                int(start_raw[3:5]),
                int(start_raw[0:2]),
            )
            end = date(
                int(end_raw[6:10]),
                int(end_raw[3:5]),
                int(end_raw[0:2]),
            )
            return "Da" if start <= date.today() <= end else "Nu"
        except (ValueError, IndexError):
            pass

    # Fallback: legacy flags
    return "Da" if index_info.get("permite_index") or index_info.get("autocit") else "Nu"


def _extract_places(raw: Any) -> list[dict[str, Any]]:
    """Return only real consumption places (those with a poc_number)."""

    def _walk(node: Any):
        if isinstance(node, dict):
            yield node
            for value in node.values():
                yield from _walk(value)
        elif isinstance(node, list):
            for item in node:
                yield from _walk(item)

    places: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in _walk(raw):
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


def _format_address_value(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, Mapping):
        inline = value.get("inline")
        if inline:
            return str(inline)
        parts: list[str] = []
        street = value.get("street")
        number = value.get("number")
        building = value.get("building")
        staircase = value.get("staircase")
        floor = value.get("floor")
        apartment = value.get("apartment")
        city = value.get("city")
        if street:
            street_part = str(street)
            if number:
                street_part += f" {number}"
            parts.append(street_part)
        if building:
            parts.append(f"Bl. {building}")
        if staircase:
            parts.append(f"Sc. {staircase}")
        if floor:
            parts.append(f"Et. {floor}")
        if apartment:
            parts.append(f"Ap. {apartment}")
        if city:
            parts.append(str(city))
        if parts:
            return ", ".join(parts)
    return str(value)


def _place_poc(place: Mapping[str, Any], index: int) -> str:
    return str(place.get("poc_number") or place.get("pocNumber") or place.get("poc") or index)


def _place_address(place: Mapping[str, Any], index: int) -> str:
    for key in ("address", "consumptionPlaceAddress", "name", "label", "site_name", "siteName"):
        formatted = _format_address_value(place.get(key))
        if formatted:
            return formatted
    return f"Loc consum {index + 1}"


def _place_contract(place: Mapping[str, Any]) -> str | None:
    return (
        place.get("contract_account")
        or place.get("contractAccount")
        or place.get("contract_account_number")
        or place.get("contractAccountNumber")
    )


def _place_division(place: Mapping[str, Any]) -> str | None:
    return place.get("division") or place.get("commodity") or place.get("type")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: EngieDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    places = _extract_places(data.get("places"))

    entities: list[SensorEntity] = [
        EngieAccountSensor(coordinator, entry, "account_places_count"),
        EngieAccountSensor(coordinator, entry, "account_profile"),
    ]

    for idx, place in enumerate(places):
        # 3 senzori de bază pentru orice loc de consum
        entities.extend(
            [
                EngiePlaceSensor(
                    coordinator,
                    entry,
                    place,
                    idx,
                    "summary",
                    "Engie – Rezumat",
                    "mdi:home-city-outline",
                ),
                EngiePlaceSensor(
                    coordinator,
                    entry,
                    place,
                    idx,
                    "address",
                    "Engie – Adresă",
                    "mdi:map-marker",
                ),
                EngiePlaceSensor(
                    coordinator,
                    entry,
                    place,
                    idx,
                    "contract",
                    "Engie – Contract",
                    "mdi:file-document-outline",
                ),
            ]
        )

        # 4 senzori suplimentari — pentru TOATE locurile
        entities.extend(
            [
                EngiePlaceDataSensor(
                    coordinator,
                    entry,
                    place,
                    idx,
                    "current_index_window",
                    "Engie – Index curent",
                    "mdi:counter",
                ),
                EngiePlaceDataSensor(
                    coordinator,
                    entry,
                    place,
                    idx,
                    "unpaid_total",
                    "Engie – Valoare factură restantă",
                    "mdi:file-document-alert-outline",
                ),
                EngiePlaceDataSensor(
                    coordinator,
                    entry,
                    place,
                    idx,
                    "invoice_archive_count",
                    "Engie – Arhivă facturi",
                    "mdi:cash-register",
                ),
                EngiePlaceDataSensor(
                    coordinator,
                    entry,
                    place,
                    idx,
                    "index_history_last",
                    "Engie – Ultimul index din istoric",
                    "mdi:history",
                ),
            ]
        )

    async_add_entities(entities, True)


# ---------------------------------------------------------------------------
# Base entity
# ---------------------------------------------------------------------------


class EngieBaseEntity(CoordinatorEntity[EngieDataCoordinator], SensorEntity):
    def __init__(self, coordinator: EngieDataCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def _account_identifier(self) -> tuple[str, str]:
        return (DOMAIN, f"account_{self._entry.entry_id}")

    @property
    def account_device_info(self) -> DeviceInfo:
        profile = (self.coordinator.data or {}).get("profile") or {}
        email = profile.get("email") or self._entry.data.get("username") or self._entry.title
        return DeviceInfo(
            identifiers={self._account_identifier},
            manufacturer="Engie România",
            model="Account",
            name=f"Engie România - {email}",
        )


# ---------------------------------------------------------------------------
# Account-level sensors
# ---------------------------------------------------------------------------


class EngieAccountSensor(EngieBaseEntity):
    def __init__(
        self, coordinator: EngieDataCoordinator, entry: ConfigEntry, sensor_key: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._sensor_key = sensor_key
        self._attr_unique_id = f"{entry.entry_id}_{sensor_key}"

    @property
    def device_info(self) -> DeviceInfo:
        return self.account_device_info

    @property
    def name(self) -> str:
        return {
            "account_places_count": "Engie – Număr locuri de consum",
            "account_profile": "Engie – Cont",
        }[self._sensor_key]

    @property
    def icon(self) -> str | None:
        return {
            "account_places_count": "mdi:counter",
            "account_profile": "mdi:account-circle-outline",
        }.get(self._sensor_key)

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        if self._sensor_key == "account_places_count":
            return len(_extract_places(data.get("places")))
        if self._sensor_key == "account_profile":
            prof = data.get("profile") or {}
            return prof.get("email") or prof.get("name") or self._entry.title
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        if self._sensor_key == "account_profile":
            prof = data.get("profile") or {}
            return {
                "attribution": ATTRIBUTION,
                "email": prof.get("email"),
                "nume": prof.get("name"),
                "telefon": prof.get("phone"),
                "last_update": data.get("last_update"),
            }
        return {"attribution": ATTRIBUTION}


# ---------------------------------------------------------------------------
# Place entity base
# ---------------------------------------------------------------------------


class EngiePlaceEntity(EngieBaseEntity):
    def __init__(
        self,
        coordinator: EngieDataCoordinator,
        entry: ConfigEntry,
        place: Mapping[str, Any],
        index: int,
    ) -> None:
        super().__init__(coordinator, entry)
        self._place = dict(place)
        self._index = index
        self._poc = _place_poc(place, index)
        self._address = _place_address(place, index)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_place_{self._poc}")},
            manufacturer="Engie România",
            model="Consumption Place",
            name=f"Engie România ({self._poc})",
            suggested_area=self._address,
            via_device=self._account_identifier,
        )

    def _place_data(self) -> dict[str, Any]:
        """Return the coordinator data slice for this place."""
        places_data = (self.coordinator.data or {}).get("places_data") or {}
        return places_data.get(self._poc) or {}

    def _base_attrs(self) -> dict[str, Any]:
        """Minimal common attributes — only clean, relevant fields."""
        pd = self._place_data()
        attrs: dict[str, Any] = {
            "attribution": ATTRIBUTION,
            "poc_number": self._poc,
        }
        address = pd.get("address") or self._address
        if address:
            attrs["adresa"] = address
        contract = (
            pd.get("contract_account_number")
            or pd.get("contract_account")
            or _place_contract(self._place)
        )
        if contract:
            attrs["cont_contract"] = contract
        division = pd.get("division") or _place_division(self._place)
        if division:
            attrs["tip_energie"] = division
        pa = pd.get("pa")
        if pa:
            attrs["pa"] = pa
        return attrs


# ---------------------------------------------------------------------------
# Basic place sensors (address, contract, summary)
# ---------------------------------------------------------------------------


class EngiePlaceSensor(EngiePlaceEntity):
    def __init__(
        self,
        coordinator: EngieDataCoordinator,
        entry: ConfigEntry,
        place: Mapping[str, Any],
        index: int,
        sensor_key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, entry, place, index)
        self._sensor_key = sensor_key
        self._attr_unique_id = f"{entry.entry_id}_place_{self._poc}_{sensor_key}"
        self._attr_name = name
        self._attr_icon = icon

    @property
    def native_value(self) -> Any:
        pd = self._place_data()
        if self._sensor_key == "summary":
            return pd.get("poc_number") or _place_division(self._place) or self._poc
        if self._sensor_key == "address":
            return pd.get("address") or self._address
        if self._sensor_key == "contract":
            return (
                pd.get("contract_account_number")
                or pd.get("contract_account")
                or _place_contract(self._place)
                or "—"
            )
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pd = self._place_data()
        attrs = self._base_attrs()

        if self._sensor_key == "summary":
            # Include contract details
            ca_num = pd.get("contract_account_number") or pd.get("contract_account")
            inst_num = pd.get("installation_number")
            if ca_num:
                attrs["numar_contract"] = ca_num
            if inst_num:
                attrs["numar_instalatie"] = inst_num

        elif self._sensor_key == "address":
            # Include structured address fields from raw place
            raw_addr = self._place.get("address") or {}
            if isinstance(raw_addr, dict):
                for field in (
                    "street",
                    "number",
                    "floor",
                    "apartment",
                    "city",
                    "district",
                    "postcode",
                ):
                    val = raw_addr.get(field)
                    if val:
                        attrs[field] = val

        elif self._sensor_key == "contract":
            # Include greenbill / email info if available
            raw_contract = self._place.get("contract_account") or {}
            if isinstance(raw_contract, dict):
                for field in ("greenbill_email", "has_greenbill", "greenbill_status"):
                    val = raw_contract.get(field)
                    if val is not None:
                        attrs[field] = val

        return attrs


# ---------------------------------------------------------------------------
# Extended place sensors (index, unpaid, archive, history)
# ---------------------------------------------------------------------------


class EngiePlaceDataSensor(EngiePlaceEntity):
    def __init__(
        self,
        coordinator: EngieDataCoordinator,
        entry: ConfigEntry,
        place: Mapping[str, Any],
        index: int,
        sensor_key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, entry, place, index)
        self._sensor_key = sensor_key
        self._attr_unique_id = f"{entry.entry_id}_place_{self._poc}_{sensor_key}"
        self._attr_name = name
        self._attr_icon = icon

    @property
    def native_value(self) -> Any:
        pd = self._place_data()

        if self._sensor_key == "current_index_window":
            info = pd.get("index_info") or {}
            return _in_reading_window(info)

        if self._sensor_key == "unpaid_total":
            unpaid = pd.get("unpaid_total")
            try:
                return float(unpaid) if unpaid is not None else 0.0
            except Exception:
                return unpaid

        if self._sensor_key == "invoice_archive_count":
            # Use consumption_count (number of invoices fetched)
            return pd.get("consumption_count") or 0

        if self._sensor_key == "index_history_last":
            return pd.get("index_history_last")

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pd = self._place_data()
        attrs = self._base_attrs()

        if self._sensor_key == "current_index_window":
            info = pd.get("index_info") or {}
            # Clean, relevant fields only
            if info.get("autocit") is not None:
                attrs["autocit"] = info["autocit"]
            if info.get("permite_index") is not None:
                attrs["permite_index"] = info["permite_index"]
            if info.get("last_index") is not None:
                attrs["ultimul_index"] = info["last_index"]
            if info.get("start_date"):
                attrs["start_citire"] = info["start_date"]
            if info.get("end_date"):
                attrs["end_citire"] = info["end_date"]

        elif self._sensor_key == "unpaid_total":
            items = pd.get("unpaid_items") or []
            if items:
                # Simplified: only invoice_number, due_date, unpaid per item
                attrs["facturi_restante"] = [
                    {
                        "numar_factura": it.get("invoice_number"),
                        "scadenta": it.get("due_date"),
                        "restant": it.get("unpaid"),
                        "total": it.get("total"),
                    }
                    for it in items
                ]
            else:
                attrs["facturi_restante"] = []

        elif self._sensor_key == "invoice_archive_count":
            # Clean "luna: suma" dict — newest first
            by_month = pd.get("consumption_by_month") or {}
            attrs.update(by_month)
            total = pd.get("consumption_total")
            if total is not None:
                attrs["total_suma_achitata"] = f"{total:.2f} lei".replace(".", ",")
            platite = pd.get("consumption_count")
            if platite is not None:
                attrs["plati_efectuate"] = platite

        elif self._sensor_key == "index_history_last":
            # Clean "luna an: index" dict — newest first
            by_month = pd.get("index_history_by_month") or {}
            attrs.update(by_month)

        return attrs
