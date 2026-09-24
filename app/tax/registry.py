"""Tax-year registry: which interview / rules apply to which tax year. A future year adds a module (copying or extending y2025) and one line here; cases keep the year they were created for."""

from app.tax import y2025

CONFIGS = {2025: y2025.CONFIG}
CURRENT_YEAR = 2025
SERVICE_SLUG = "tax-preparation"


def config_for(year):
    return CONFIGS.get(int(year)) or CONFIGS[CURRENT_YEAR]
