"""PkgForge sidecar facade — implementation lives in core/api/* (F2.2 split).

All public and test-facing names are re-exported here so
``import core.api_server`` keeps working unchanged.
"""
from core.api import *
from core.api import __all__ as _api_all__
from core.api import (
    handlers_pipeline,
    handlers_queue,
    handlers_repo,
    handlers_security,
    handlers_system,
    handlers_tools,
    http,
    protocol,
    registry,
    transport,
)

__all__ = list(_api_all__) + [
    "transport", "protocol", "registry", "http",
    "handlers_pipeline", "handlers_security", "handlers_system",
    "handlers_repo", "handlers_queue", "handlers_tools",
]
