"""
Importing this package triggers self-registration of every adapter into
BaseIntegration.ADAPTER_REGISTRY (FR-004).
"""
from app.integrations.base import ADAPTER_REGISTRY, BaseIntegration  # noqa: F401
from app.integrations import github_adapter  # noqa: F401
from app.integrations import taiga_adapter  # noqa: F401
from app.integrations import discord_adapter  # noqa: F401
from app.integrations import simulated_monitoring_adapter  # noqa: F401
