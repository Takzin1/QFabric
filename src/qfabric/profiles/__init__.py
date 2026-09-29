"""Backend-specific planning profiles.

Profiles translate QFabric protocol messages into backend-facing execution plans.
They do not imply physical-hardware compatibility or perform hardware I/O.
"""

from .qick import (
    QICK_PROFILE_VERSION,
    QICK_REFERENCE_COMMIT,
    QICK_REFERENCE_REPOSITORY,
    QickCall,
    QickExecutionPlan,
    QickGeneratorBinding,
    QickPlanAdapter,
)

__all__ = [
    "QICK_PROFILE_VERSION",
    "QICK_REFERENCE_COMMIT",
    "QICK_REFERENCE_REPOSITORY",
    "QickCall",
    "QickExecutionPlan",
    "QickGeneratorBinding",
    "QickPlanAdapter",
]
