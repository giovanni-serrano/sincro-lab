"""Scientific analyses for the classical SincroLab SMIB model."""

from sincrolab.analysis.equal_area import (
    DEFAULT_AREA_TOLERANCE_PU_RAD,
    EqualAreaAssessment,
    EqualAreaStatus,
    assess_equal_area,
)
from sincrolab.analysis.first_swing import (
    FirstSwingAssessment,
    FirstSwingEventBracket,
    FirstSwingReason,
    FirstSwingStatus,
    assess_smib_first_swing,
)

__all__ = [
    "DEFAULT_AREA_TOLERANCE_PU_RAD",
    "EqualAreaAssessment",
    "EqualAreaStatus",
    "FirstSwingAssessment",
    "FirstSwingEventBracket",
    "FirstSwingReason",
    "FirstSwingStatus",
    "assess_equal_area",
    "assess_smib_first_swing",
]
