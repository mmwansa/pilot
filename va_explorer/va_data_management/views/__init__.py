from .vae_views import (
    Index,
    Show,
    Edit,
    Reset,
    RevertLatest,
    RunCodingAlgorithm,
    Delete,
    DeleteAll,
)
from .households import (
    Households,
    HouseholdDetail,
    HouseholdEdit,
    HouseholdDelete,
    HouseholdDeleteAll,
)

from .pregnancies import (
    Pregnancies,
    PregnancyDetail,
    PregnancyEdit,
    PregnancyDelete,
    PregnancyDeleteAll,
)

from .pregnancy_outcomes import (
    PregnancyOutcomes,
    PregnancyOutcomeDetail,
    PregnancyOutcomeEdit,
    PregnancyOutcomeDelete,
    PregnancyOutcomeDeleteAll,
)

from .deaths import (
    Deaths,
    DeathDetail,
    DeathEdit,
    DeathDelete,
    DeathDeleteAll,
)

__all__ = [
    'Index',
    'Show',
    'Edit',
    'Reset',
    'RevertLatest',
    'RunCodingAlgorithm',
    'Delete',
    'DeleteAll',
    'Households',
    'HouseholdDetail',
    'HouseholdEdit',
    'HouseholdDelete',
    'HouseholdDeleteAll',
    'Pregnancies',
    'PregnancyDetail',
    'PregnancyEdit',
    'PregnancyDelete',
    'PregnancyDeleteAll',
    'PregnancyOutcomes',
    'PregnancyOutcomeDetail',
    'PregnancyOutcomeEdit',
    'PregnancyOutcomeDelete',
    'PregnancyOutcomeDeleteAll',
    'Deaths',
    'DeathDetail',
    'DeathEdit',
    'DeathDelete',
    'DeathDeleteAll',
]
