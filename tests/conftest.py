import sys
import os
from unittest.mock import MagicMock

# Make the custom_components package importable from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub out homeassistant so __init__.py can be imported without a full HA install.
# The live tests only exercise api.py and const.py, which have no HA dependencies.
_HA_MODULES = [
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.core",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.device_registry",
    "homeassistant.components",
    "homeassistant.components.button",
    "homeassistant.components.light",
]
for _mod in _HA_MODULES:
    sys.modules[_mod] = MagicMock()
