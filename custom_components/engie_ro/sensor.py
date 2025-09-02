from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, MANUFACTURER, DEVICE_NAME_FMT
from .coordinator import EngieCoordinator

PARALLEL_UPDATES = 0

@dataclass
class EngieSensorDescription:
    key: str
    name: str
    icon: str | None = None
    native_unit: str | None = None

SENSORS: list[EngieSensorDescription] = [
    EngieSensorDescription("current_index.value", "Index curent", icon="mdi:counter", native_unit=UnitOfEnergy.KILO_WATT_HOUR),
    EngieSensorDescription("billing_history.last.amount", "Ultima factură", icon="mdi:receipt-text"),
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: EngieCoordinator = hass.data[DOMAIN][entry.entry_id]

    pa = (coordinator.data or {}).get("overview", {}).get("pa", "PA_UNKNOWN")
    device = DeviceInfo(
        identifiers={(DOMAIN, f"pa:{pa}")},
        name=DEVICE_NAME_FMT.format(pa=pa),
        manufacturer=MANUFACTURER,
        configuration_url="https://my.engie.ro/"
    )

    entities: list[EngieSensor] = []
    for desc in SENSORS:
        entities.append(EngieSensor(coordinator, entry.entry_id, device, desc, pa))
    async_add_entities(entities)

class EngieSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: EngieCoordinator, entry_id: str, device: DeviceInfo, desc: EngieSensorDescription, pa: str):
        self.coordinator = coordinator
        self.entity_description = desc
        self._attr_unique_id = f"{entry_id}_{pa}_{desc.key}"
        self._attr_device_info = device
        if desc.native_unit:
            self._attr_native_unit_of_measurement = desc.native_unit
        if desc.icon:
            self._attr_icon = desc.icon

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        return dig(data, self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.coordinator.data or {}
        history = data.get("billing_history", {})
        return {
            "billing_history": history.get("items"),
            "poc": dig(data, "overview.poc"),
            "division": dig(data, "overview.division"),
        }

def dig(data: dict[str, Any], path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur
