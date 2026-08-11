"""
Importing this package triggers self-registration of every adapter into
BaseIntegration.ADAPTER_REGISTRY (FR-004).

Product decision: GitHub is the sole integration. Taiga, Discord, and the
simulated monitoring adapter were dropped to keep the product's value
proposition sharp - real, live GitHub data (via GitHubAdapter/github_sync)
rather than a smorgasbord of integrations that need accounts most users
don't have. Incidents/alerts still work without a monitoring adapter -
see app.demo.seed for how Alert rows get created (directly, or in the
future from GitHub deployment status events).
"""
from app.integrations.base import ADAPTER_REGISTRY, BaseIntegration  # noqa: F401
from app.integrations import github_adapter  # noqa: F401
