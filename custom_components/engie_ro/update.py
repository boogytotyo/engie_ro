from __future__ import annotations
import logging
from typing import Any, Dict
from .api import EngieClient, EngieHTTPError, EngieUnauthorized

_LOGGER = logging.getLogger(__name__)

async def safe_call(client: EngieClient, fn, *args, **kwargs) -> Any:
    try:
        return await fn(*args, **kwargs)
    except EngieUnauthorized as e:
        _LOGGER.debug("Unauthorized: %s", e)
        raise
    except EngieHTTPError as e:
        _LOGGER.debug("HTTP error: %s", e)
        return None
    except Exception as e:
        _LOGGER.debug("Generic error: %s", e)
        return None

async def update_all(client: EngieClient, keys: Dict[str, Any]) -> Dict[str, Any]:
    """
    Exemplu de orchestrare a update-urilor (placeholder).
    Păstrează cheile pentru senzori, nu modifica structura lor.
    """
    data: Dict[str, Any] = {}
    # populate keys one by one if you already have logic in your repo
    # here we only keep placeholders to avoid altering logic
    for k in ("user", "contracts", "indexes", "consumption", "balance", "invoices"):
        data[k] = data.get(k, {})
    return data
