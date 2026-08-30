"""Continuous right-hand side of the classical SMIB swing equation."""

from math import pi

import numpy as np
from numpy.typing import NDArray

from sincrolab.models.power_angle import electrical_power_pu
from sincrolab.models.smib import SMIBParameters


def smib_swing_rhs(
    time_s: float,
    state: NDArray[np.float64],
    parameters: SMIBParameters,
) -> NDArray[np.float64]:
    """Evaluate the autonomous classical SMIB swing equation.

    ``state`` is ordered as ``[delta_rad, omega_dev_pu]``, where
    ``omega_dev_pu = (omega - omega_s) / omega_s`` and
    ``omega_s = 2 * pi * f_base_hz``. The returned derivatives use the same
    order and have units ``[rad/s, pu/s]``. ``time_s`` is accepted to preserve
    the generic ``f(t, y)`` RHS contract.
    """
    del time_s

    state_array = np.asarray(state, dtype=np.float64)
    if state_array.shape != (2,):
        raise ValueError(
            "state must have shape (2,) ordered as "
            "[delta_rad, omega_dev_pu]"
        )
    if not np.all(np.isfinite(state_array)):
        raise ValueError("state values must be finite")

    delta_rad = float(state_array[0])
    omega_dev_pu = float(state_array[1])
    omega_s_rad_per_s = 2.0 * pi * parameters.f_base_hz
    Pe_pu = electrical_power_pu(
        delta_rad=delta_rad,
        Pmax_pu=parameters.Pmax_pu,
    )

    d_delta_rad_dt = omega_s_rad_per_s * omega_dev_pu
    d_omega_dev_pu_dt = (
        parameters.Pm_pu - Pe_pu - parameters.D_pu * omega_dev_pu
    ) / (2.0 * parameters.H_s)

    return np.array([d_delta_rad_dt, d_omega_dev_pu_dt], dtype=np.float64)
