"""Run host imports against an isolated root, never the live AstrBot data."""

import copy
import json
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOST = Path(os.environ.get("HUMANIZATION_ASTRBOT_SOURCE", ROOT.parents[2]))
# Keep artifacts for inspection; do not recursively clean user directories.
os.environ["ASTRBOT_ROOT"] = tempfile.mkdtemp(prefix="humanization-host-")
sys.dont_write_bytecode = True
sys.path.insert(0, str(HOST))
package = types.ModuleType("humanization_test")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package


@pytest.fixture
def log(tmp_path):
    from humanization_test.utils.plugin_log import PluginLog

    return PluginLog(tmp_path / "log", False, Mock(), ZoneInfo("Asia/Shanghai"))


@pytest.fixture
def tmp_path():
    return Path(tempfile.mkdtemp(prefix="humanization-test-"))


@pytest.fixture
def config():
    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    return {
        group: {
            key: copy.deepcopy(item["default"]) for key, item in block["items"].items()
        }
        for group, block in schema.items()
    }
