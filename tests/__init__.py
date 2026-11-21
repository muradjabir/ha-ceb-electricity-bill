"""Tests initialization."""
import sys
from unittest.mock import MagicMock

# Allow running tests in lightweight environments without Home Assistant installed
if "homeassistant" not in sys.modules:
    for mod in (
        "homeassistant",
        "homeassistant.components",
        "homeassistant.components.sensor",
        "homeassistant.components.number",
        "homeassistant.config_entries",
        "homeassistant.const",
        "homeassistant.core",
        "homeassistant.data_entry_flow",
        "homeassistant.exceptions",
        "homeassistant.helpers",
        "homeassistant.helpers.entity",
        "homeassistant.helpers.entity_platform",
        "homeassistant.helpers.event",
        "homeassistant.helpers.restore_state",
        "homeassistant.helpers.selector",
        "homeassistant.helpers.update_coordinator",
    ):
        sys.modules.setdefault(mod, MagicMock())
