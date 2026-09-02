import copy
import json

import pytest

from backend.config import DEFAULT_ROOM_CONFIG
from backend.importers.room_config_json import parse_room_config_json_bytes


def parse(payload):
    return parse_room_config_json_bytes(json.dumps(payload, ensure_ascii=False).encode())


def test_old_room_config_without_subsite_remains_valid():
    payload = copy.deepcopy(DEFAULT_ROOM_CONFIG)
    payload.pop("subsite_name", None)
    result = parse(payload)
    assert result.errors == []
    assert result.config.subsite_name is None


@pytest.mark.parametrize("value", [None, "", "   "])
def test_empty_subsite_means_no_alias(value):
    payload = copy.deepcopy(DEFAULT_ROOM_CONFIG)
    payload["subsite_name"] = value
    result = parse(payload)
    assert result.errors == []
    assert result.config.subsite_name is None


def test_valid_subsite_is_trimmed():
    payload = copy.deepcopy(DEFAULT_ROOM_CONFIG)
    payload["subsite_name"] = "  test-conf_2  "
    result = parse(payload)
    assert result.errors == []
    assert result.config.subsite_name == "test-conf_2"


@pytest.mark.parametrize("value", ["bad/path", "bad path", "Bad", "событие", "admin", "health", "ws", "listener.js", "vendor"])
def test_invalid_or_reserved_subsite_is_rejected(value):
    payload = copy.deepcopy(DEFAULT_ROOM_CONFIG)
    payload["subsite_name"] = value
    result = parse(payload)
    assert result.config is None
    assert any(error.field == "subsite_name" for error in result.errors)


def test_non_string_subsite_is_rejected():
    payload = copy.deepcopy(DEFAULT_ROOM_CONFIG)
    payload["subsite_name"] = 123
    assert parse(payload).errors[0].code == "INVALID_SUBSITE_NAME"
