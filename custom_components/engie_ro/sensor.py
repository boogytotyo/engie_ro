from __future__ import annotations
from typing import Any, Dict
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, ATTRIBUTION
from .coordinator import EngieDataCoordinator

SENSOR_KEY_USER = "user"
SENSOR_KEY_CONTRACTS = "contracts"
SENSOR_KEY_INDEXES = "indexes"
SENSOR_KEY_CONSUMPTION = "consumption"
SENSOR_KEY_BALANCE = "balance"
SENSOR_KEY_INVOICES = "invoices"

SENSORS = [
    SENSOR_KEY_USER,
    SENSOR_KEY_CONTRACTS,
    SENSOR_KEY_INDEXES,
    SENSOR_KEY_CONSUMPTION,
    SENSOR_KEY_BALANCE,
    SENSOR_KEY_INVOICES,
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coord: EngieDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[EngieSensor] = [EngieSensor(coord, key) for key in SENSORS]
    async_add_entities(entities)

class EngieSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EngieDataCoordinator, key: str) -> None:
        self._coordinator = coordinator
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}-{key}"
        self._attr_name = f"Engie {key}"
        self._attr_attribution = ATTRIBUTION

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._coordinator.entry.entry_id)},
            name="Engie România",
            manufacturer="Engie",
            model="Engie API",
        )

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> Any:
        data = self._coordinator.data or {}
        value = data.get(self._key)
        if isinstance(value, dict | list):
            return len(value)
        return value

    @property
    def extra_state_attributes(self) -> Dict[str, Any] | None:
        data = self._coordinator.data or {}
        val = data.get(self._key)
        if isinstance(val, dict | list):
            return {"data": val}
        return None
