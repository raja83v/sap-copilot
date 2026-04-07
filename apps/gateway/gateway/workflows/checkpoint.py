"""In-memory checkpoint saver for LangGraph workflows.

Stores graph state so workflows can be interrupted (for user approval)
and resumed later. Uses an in-memory dict keyed by workflow_id.

For production persistence across gateway restarts, this can be extended to
use Convex or a database backend. The current implementation survives within
a single gateway process lifetime, which is sufficient for the approval flow.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger("gateway.workflows.checkpoint")


def create_checkpoint_saver() -> MemorySaver:
    """Create a LangGraph checkpoint saver.

    Uses the built-in MemorySaver which stores checkpoints in-process.
    This is sufficient for the current single-gateway deployment.
    """
    return MemorySaver()


# Singleton checkpoint saver for the gateway process
checkpoint_saver = create_checkpoint_saver()
