from __future__ import annotations

import pytest  # 👈 asta lipsește

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Activează automat integrațiile custom în teste."""
    yield
