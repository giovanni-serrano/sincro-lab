from dataclasses import FrozenInstanceError, fields

import numpy as np
import pytest

from sincrolab.application import (
    SMIBSimulationResult,
    simulate_smib_equilibrium,
    simulate_smib_free_disturbance,
)
from sincrolab.application.equilibrium import (
    SMIBSimulationResult as EquilibriumModuleResult,
)
from sincrolab.application.results import (
    SMIBSimulationResult as ResultsModuleResult,
)
from sincrolab.models import SMIBParameters


def _parameters() -> SMIBParameters:
    return SMIBParameters(
        H_s=3.5,
        D_pu=0.2,
        f_base_hz=60.0,
        Pm_pu=0.7,
        Pmax_pu=1.2,
    )


def _valid_series() -> dict[str, np.ndarray]:
    return {
        "time_s": np.array([0, 1, 2], dtype=np.int64),
        "delta_rad": np.array([0.6, 0.61, 0.62], dtype=np.float32),
        "omega_dev_pu": np.array([0.0, 0.001, -0.001], dtype=np.float32),
    }


def _assert_result_contract(result: SMIBSimulationResult) -> None:
    series = (result.time_s, result.delta_rad, result.omega_dev_pu)

    assert all(values.ndim == 1 for values in series)
    assert all(values.dtype == np.float64 for values in series)
    assert result.time_s.shape == result.delta_rad.shape
    assert result.time_s.shape == result.omega_dev_pu.shape
    assert result.time_s.size >= 1
    assert all(np.all(np.isfinite(values)) for values in series)
    assert np.all(np.diff(result.time_s) > 0.0)
    assert all(not values.flags.writeable for values in series)


def test_result_has_exact_scientific_series_and_neutral_public_location() -> None:
    assert [field.name for field in fields(SMIBSimulationResult)] == [
        "time_s",
        "delta_rad",
        "omega_dev_pu",
    ]
    assert SMIBSimulationResult is ResultsModuleResult
    assert SMIBSimulationResult is EquilibriumModuleResult


def test_result_normalizes_series_to_float64_read_only_vectors() -> None:
    result = SMIBSimulationResult(**_valid_series())

    _assert_result_contract(result)


def test_result_rejects_series_with_different_lengths() -> None:
    series = _valid_series()
    series["omega_dev_pu"] = np.array([0.0, 0.001])

    with pytest.raises(ValueError, match="same length"):
        SMIBSimulationResult(**series)


@pytest.mark.parametrize("field_name", ["time_s", "delta_rad", "omega_dev_pu"])
def test_result_rejects_multidimensional_series(field_name: str) -> None:
    series = _valid_series()
    series[field_name] = np.array([[0.0, 1.0, 2.0]])

    with pytest.raises(ValueError, match=rf"{field_name} must be one-dimensional"):
        SMIBSimulationResult(**series)


@pytest.mark.parametrize("field_name", ["time_s", "delta_rad", "omega_dev_pu"])
def test_result_rejects_nonfinite_series(field_name: str) -> None:
    series = _valid_series()
    series[field_name] = np.array([0.0, np.nan, 2.0])

    with pytest.raises(ValueError, match=rf"{field_name} values must be finite"):
        SMIBSimulationResult(**series)


def test_result_rejects_empty_series() -> None:
    empty = np.array([], dtype=np.float64)

    with pytest.raises(ValueError, match="at least one sample"):
        SMIBSimulationResult(
            time_s=empty,
            delta_rad=empty,
            omega_dev_pu=empty,
        )


@pytest.mark.parametrize(
    "time_s",
    [
        np.array([0.0, 0.0, 1.0]),
        np.array([0.0, 2.0, 1.0]),
    ],
)
def test_result_rejects_time_that_is_not_strictly_increasing(
    time_s: np.ndarray,
) -> None:
    series = _valid_series()
    series["time_s"] = time_s

    with pytest.raises(ValueError, match="time_s must be strictly increasing"):
        SMIBSimulationResult(**series)


def test_result_owns_immutable_snapshots_of_input_series() -> None:
    source = {
        name: np.array(values, dtype=np.float64, copy=True)
        for name, values in _valid_series().items()
    }
    expected = {name: values.copy() for name, values in source.items()}
    result = SMIBSimulationResult(**source)

    for values in source.values():
        values[:] = -99.0

    for name, expected_values in expected.items():
        result_values = getattr(result, name)
        np.testing.assert_array_equal(result_values, expected_values)
        assert not np.shares_memory(result_values, source[name])
        with pytest.raises(ValueError, match="read-only"):
            result_values[0] = 99.0
        with pytest.raises(ValueError, match="WRITEABLE"):
            result_values.setflags(write=True)

    with pytest.raises(FrozenInstanceError):
        result.time_s = np.array([0.0])  # type: ignore[misc]


@pytest.mark.parametrize("simulation_name", ["equilibrium", "free_disturbance"])
def test_public_simulations_return_the_shared_result_contract(
    simulation_name: str,
) -> None:
    common_args = {
        "t_start_s": 0.0,
        "t_end_s": 1.0,
        "dt_s": 1.0 / 64.0,
    }
    if simulation_name == "equilibrium":
        result = simulate_smib_equilibrium(_parameters(), **common_args)
    else:
        result = simulate_smib_free_disturbance(
            _parameters(),
            delta_offset_rad=0.05,
            **common_args,
        )

    assert isinstance(result, SMIBSimulationResult)
    _assert_result_contract(result)
