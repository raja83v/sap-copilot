"""Workflow router — classifies user intent into a WorkflowType or simple_chat.

Uses the LLM with structured output to decide whether a user message should
trigger a multi-agent workflow or be handled as a simple chat query.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from ..routes.llm import get_litellm_api_key, get_litellm_base_url
from ..config import settings
from .state import WorkflowType

logger = logging.getLogger("gateway.workflows.router")

RoutingResult = WorkflowType | Literal["simple_chat"]

# All recognised workflow types for the prompt
_WORKFLOW_DESCRIPTIONS = {
    "create_report": "Create a new ABAP report / program",
    "create_class": "Create a new ABAP class (OO)",
    "create_cds_view": "Create a new CDS view / data definition",
    "create_function_module": "Create a new function module / function group",
    "create_table": "Create a new transparent database table",
    "create_data_element": "Create a new data element and/or domain",
    "create_interface": "Create a new ABAP interface",
    "create_rap_bo": "Create a RAP Business Object (CDS, behavior, projection, service)",
    "create_ui5_app": "Create or modify a UI5/BSP application",
    "enhance_object": "Add methods, attributes, or features to an existing class/object",
    "code_review": "Review and fix existing ABAP code (ATC checks, code quality)",
    "transport_management": "Manage transports (create, release, add objects)",
    "debug_diagnose": "Debug a runtime issue, analyse dumps or traces",
    "refactor_object": "Refactor / restructure an existing ABAP object",
    "performance_analysis": "Analyse performance traces, SQL traces, call graphs for bottlenecks",
    "dump_analysis": "Investigate runtime dumps (ST22), find root cause and suggest fixes",
    "mass_activation": "Activate multiple objects across packages",
    "git_operations": "abapGit operations (pull, push, stage, link repository)",
    "documentation": "Generate technical documentation for ABAP objects",
    "migration": "Migrate objects between packages or manage package reassignment",
    "test_creation": "Create ABAP Unit test classes for existing objects",
    "amdp_creation": "Create an AMDP class with SQL Script procedures",
}

_ROUTING_PROMPT = """\
You are an intent classifier for SAP ABAP development requests.
Given the user message, decide whether it requires a multi-step workflow or
can be answered with a simple chat response (reading data, answering questions,
listing objects, etc.).

If a workflow is needed, return the most appropriate type from this list:
{workflow_list}

If no workflow is needed (the user is just asking a question, reading data,
searching objects, etc.), return "simple_chat".

Respond with ONLY a JSON object: {{"type": "<workflow_type_or_simple_chat>"}}
"""


async def classify_intent(user_message: str) -> RoutingResult:
    """Classify the user's message into a workflow type or simple_chat."""
    from openai import AsyncOpenAI

    base_url = get_litellm_base_url()
    api_key = get_litellm_api_key() or "not-needed"
    client = AsyncOpenAI(base_url=f"{base_url}/v1", api_key=api_key)

    workflow_list = "\n".join(
        f"- {k}: {v}" for k, v in _WORKFLOW_DESCRIPTIONS.items()
    )
    system_prompt = _ROUTING_PROMPT.format(workflow_list=workflow_list)

    try:
        response = await client.chat.completions.create(
            model=settings.litellm_default_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            max_tokens=50,
        )
        content = (response.choices[0].message.content or "").strip()

        # Parse routing result
        try:
            parsed = json.loads(content)
            intent = parsed.get("type", "simple_chat")
        except json.JSONDecodeError:
            # Fallback: look for a known type in the raw text
            intent = "simple_chat"
            for wf_type in _WORKFLOW_DESCRIPTIONS:
                if wf_type in content:
                    intent = wf_type
                    break

        if intent not in _WORKFLOW_DESCRIPTIONS and intent != "simple_chat":
            logger.warning("Unknown intent '%s' — falling back to simple_chat", intent)
            intent = "simple_chat"

        logger.info("Intent classified: '%s' → %s", user_message[:80], intent)
        return intent  # type: ignore[return-value]

    except Exception as e:
        logger.error("Intent classification failed: %s — falling back to simple_chat", e)
        return "simple_chat"
