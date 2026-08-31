"""Classical SMIB power-angle relations.

Reference: Glover et al., *Power System Analysis and Design*, 7th ed., Ch. 12.
"""

from math import asin, isfinite, sin


def electrical_power_pu(delta_rad: float, Pmax_pu: float) -> float:
    """Return ``Pe_pu`` for an angle in radians and powers in per unit."""
    if not isfinite(Pmax_pu) or Pmax_pu < 0.0:
        raise ValueError(
            "Pmax_pu must be finite and greater than or equal to zero"
        )

    return Pmax_pu * sin(delta_rad)


def equilibrium_angle_rad(Pm_pu: float, Pmax_pu: float) -> float:
    """Return the principal equilibrium angle for powers in per unit."""
    return _principal_equilibrium_angle_rad(
        Pm_pu,
        Pmax_pu,
        Pmax_name="Pmax_pu",
    )


def initial_equilibrium_angle_rad(
    Pm_pu: float,
    Pmax_prefault_pu: float,
) -> float:
    """Return the principal ``delta0_rad`` for prefault powers in per unit."""
    return _principal_equilibrium_angle_rad(
        Pm_pu,
        Pmax_prefault_pu,
        Pmax_name="Pmax_prefault_pu",
    )


def _principal_equilibrium_angle_rad(
    Pm_pu: float,
    Pmax_pu: float,
    *,
    Pmax_name: str,
) -> float:
    if not isfinite(Pmax_pu) or Pmax_pu <= 0.0:
        raise ValueError(
            f"{Pmax_name} must be finite and greater than zero"
        )

    power_ratio = Pm_pu / Pmax_pu
    if not isfinite(power_ratio) or not -1.0 <= power_ratio <= 1.0:
        raise ValueError(f"Pm_pu / {Pmax_name} must be within [-1, 1]")

    return asin(power_ratio)
