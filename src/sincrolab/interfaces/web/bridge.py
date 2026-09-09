"""Explicit JSON boundary to H26, shared by CPython and browser Pyodide.

The bridge has no session, scientific rules, or alternate case definitions.
Every guided execution carries a prediction validated by H26/H25 before the
existing PreparedGuidedAttempt is executed. Exceptions are transport errors,
never scientific classifications.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
import json
from math import isfinite

import sincrolab.application.portable as portable


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("Expected a JSON object")
    return value


def _dto_values(value: object, dto_type: type) -> dict[str, object]:
    data = dict(_mapping(value))
    version = data.pop("schema_version", None)
    if type(version) is not int or version != portable.PORTABLE_SCHEMA_VERSION:
        raise ValueError("Unsupported portable schema_version")
    if set(data) != {field.name for field in fields(dto_type)}:
        raise ValueError("Configuration fields do not match the portable DTO")
    return data


def _numeric_dto(value: object, dto_type: type) -> object:
    data = _dto_values(value, dto_type)
    for number in data.values():
        if type(number) not in (int, float) or not isfinite(number):
            raise ValueError("Configuration requires finite JSON numbers")
    return dto_type(**data)


def _configuration(value: object) -> portable.SimulationConfigDTO:
    data = _dto_values(value, portable.SimulationConfigDTO)
    data["parameters"] = _numeric_dto(data["parameters"], portable.SMIBParametersDTO)
    data["initial_state"] = _numeric_dto(data["initial_state"], portable.SMIBInitialStateDTO)
    data["network"] = _numeric_dto(data["network"], portable.SMIBTransientNetworkDTO)
    for key in ("t_start_s", "t_end_s", "dt_s"):
        if type(data[key]) not in (int, float) or not isfinite(data[key]):
            raise ValueError("Time inputs require finite JSON numbers")
    return portable.SimulationConfigDTO(**data)


def dispatch(operation: str, payload: object = None) -> object:
    """Return canonical JSON-friendly payloads without presentation rounding."""
    data = _mapping({} if payload is None else payload)
    if operation == "learning_content":
        result = portable.get_learning_content()
    elif operation == "capabilities":
        result = portable.get_capabilities()
    elif operation == "guided_list":
        result = portable.list_guided_cases()
    elif operation == "guided_show":
        result = portable.get_guided_case(data["case_id"])
    elif operation == "guided_hints":
        result = portable.get_guided_hints(data["case_id"], data["count"])
    elif operation == "guided_solution":
        result = portable.get_guided_solution(data["case_id"])
    elif operation == "guided_run":
        result = portable.run_guided_attempt(portable.GuidedAttemptRequest.from_dict(data))
    elif operation == "evaluate_transient":
        result = portable.evaluate_transient(_configuration(data))
    else:
        raise ValueError("Unknown web bridge operation")
    return json.loads(portable.dumps_portable(result, indent=None))


def dispatch_json(operation: str, payload_json: str = "{}") -> str:
    """Transport failures separately from successful canonical result payloads."""
    try:
        data = dispatch(operation, json.loads(payload_json))
        envelope = {"ok": True, "data": data}
    except (ValueError, TypeError, KeyError) as error:
        envelope = {"ok": False, "error": {
            "kind": "invalid_input", "detail": str(error),
        }}
    except RuntimeError as error:
        envelope = {"ok": False, "error": {
            "kind": "portable_error", "detail": str(error),
        }}
    except Exception as error:
        envelope = {"ok": False, "error": {
            "kind": "unexpected", "detail": type(error).__name__,
        }}
    return json.dumps(envelope, ensure_ascii=False, allow_nan=False)
