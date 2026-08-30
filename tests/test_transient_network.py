from dataclasses import FrozenInstanceError, fields
from math import nextafter

import pytest

from sincrolab.models import SMIBNetworkState, SMIBTransientNetwork


def _network(**overrides: float) -> SMIBTransientNetwork:
    values = {
        "Pmax_prefault_pu": 1.2,
        "Pmax_fault_pu": 0.2,
        "Pmax_postfault_pu": 0.9,
        "t_fault_s": 0.1,
        "t_clear_s": 0.25,
    }
    values.update(overrides)
    return SMIBTransientNetwork(**values)


def test_transient_network_has_explicit_immutable_domain_contract() -> None:
    network = _network()

    assert [field.name for field in fields(network)] == [
        "Pmax_prefault_pu",
        "Pmax_fault_pu",
        "Pmax_postfault_pu",
        "t_fault_s",
        "t_clear_s",
    ]
    with pytest.raises(FrozenInstanceError):
        network.t_clear_s = 0.3  # type: ignore[misc]


def test_zero_fault_transfer_capability_is_valid() -> None:
    network = _network(Pmax_fault_pu=0.0)

    assert network.Pmax_at(network.t_fault_s) == 0.0


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"t_fault_s": -0.1}, "t_fault_s"),
        ({"t_fault_s": float("nan")}, "t_fault_s"),
        ({"t_fault_s": float("inf")}, "t_fault_s"),
        ({"t_fault_s": float("-inf")}, "t_fault_s"),
        ({"t_clear_s": 0.1}, "t_clear_s"),
        ({"t_clear_s": 0.05}, "t_clear_s"),
        ({"t_clear_s": float("nan")}, "t_clear_s"),
        ({"t_clear_s": float("inf")}, "t_clear_s"),
        ({"t_clear_s": float("-inf")}, "t_clear_s"),
    ],
)
def test_transient_network_rejects_invalid_event_times(
    overrides: dict[str, float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _network(**overrides)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("Pmax_prefault_pu", 0.0),
        ("Pmax_prefault_pu", -0.1),
        ("Pmax_fault_pu", -0.1),
        ("Pmax_postfault_pu", 0.0),
        ("Pmax_postfault_pu", -0.1),
        *[
            (field_name, nonfinite)
            for field_name in (
                "Pmax_prefault_pu",
                "Pmax_fault_pu",
                "Pmax_postfault_pu",
            )
            for nonfinite in (float("nan"), float("inf"), float("-inf"))
        ],
    ],
)
def test_transient_network_rejects_invalid_transfer_capabilities(
    field_name: str,
    invalid_value: float,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        _network(**{field_name: invalid_value})


@pytest.mark.parametrize(
    ("time_s", "expected_state", "expected_Pmax_pu"),
    [
        (nextafter(0.1, float("-inf")), SMIBNetworkState.PREFAULT, 1.2),
        (0.1, SMIBNetworkState.FAULT, 0.2),
        (0.2, SMIBNetworkState.FAULT, 0.2),
        (nextafter(0.25, float("-inf")), SMIBNetworkState.FAULT, 0.2),
        (0.25, SMIBNetworkState.POSTFAULT, 0.9),
        (nextafter(0.25, float("inf")), SMIBNetworkState.POSTFAULT, 0.9),
    ],
)
def test_state_and_Pmax_selection_use_exact_event_boundaries(
    time_s: float,
    expected_state: SMIBNetworkState,
    expected_Pmax_pu: float,
) -> None:
    network = _network()

    assert network.state_at(time_s) is expected_state
    assert network.Pmax_at(time_s) == expected_Pmax_pu


@pytest.mark.parametrize(
    "invalid_time_s",
    [float("nan"), float("inf"), float("-inf")],
)
@pytest.mark.parametrize("method_name", ["state_at", "Pmax_at"])
def test_network_queries_reject_nonfinite_times(
    method_name: str,
    invalid_time_s: float,
) -> None:
    method = getattr(_network(), method_name)

    with pytest.raises(ValueError, match="time_s must be finite"):
        method(invalid_time_s)
