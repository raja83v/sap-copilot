"""DSL module — YAML-based workflow definitions for multi-step ABAP operations.

Allows users to define complex multi-step operations (create package,
create objects, write source, activate) as declarative YAML workflows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("vsp.dsl")


class StepType(str, Enum):
    """Supported DSL step types."""

    CREATE = "create"
    WRITE = "write"
    EDIT = "edit"
    DELETE = "delete"
    ACTIVATE = "activate"
    TEST = "test"
    ATC = "atc"
    LOCK = "lock"
    UNLOCK = "unlock"
    TRANSPORT = "transport"
    CUSTOM = "custom"


@dataclass
class Step:
    """A single operation step in a workflow."""

    type: StepType
    name: str = ""
    object_type: str = ""
    object_name: str = ""
    package: str = ""
    transport: str = ""
    source: str = ""
    search: str = ""
    replace: str = ""
    description: str = ""
    method: str = ""
    activate: bool = True
    parameters: dict[str, Any] = field(default_factory=dict)
    # Control flow
    continue_on_error: bool = False
    condition: str = ""  # Simple expression evaluated at runtime


@dataclass
class Workflow:
    """A multi-step workflow definition."""

    name: str
    description: str = ""
    version: str = "1.0"
    steps: list[Step] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    # Rollback support
    rollback_on_failure: bool = True


@dataclass
class StepResult:
    """Result of executing a single step."""

    step: Step
    success: bool
    output: str = ""
    error: str = ""
    elapsed_ms: float = 0.0


@dataclass
class WorkflowResult:
    """Result of executing a complete workflow."""

    workflow: Workflow
    success: bool
    step_results: list[StepResult] = field(default_factory=list)
    total_elapsed_ms: float = 0.0

    @property
    def failed_steps(self) -> list[StepResult]:
        return [r for r in self.step_results if not r.success]

    @property
    def summary(self) -> str:
        total = len(self.step_results)
        passed = sum(1 for r in self.step_results if r.success)
        return (
            f"Workflow '{self.workflow.name}': {passed}/{total} steps passed "
            f"({self.total_elapsed_ms:.0f}ms)"
        )


def parse_workflow(yaml_text: str) -> Workflow:
    """Parse a YAML workflow definition into a Workflow object."""
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required for DSL workflows: pip install pyyaml")

    data = yaml.safe_load(yaml_text)
    if not isinstance(data, dict):
        raise ValueError("Workflow YAML must be a mapping")

    wf = Workflow(
        name=data.get("name", "unnamed"),
        description=data.get("description", ""),
        version=str(data.get("version", "1.0")),
        variables=data.get("variables", {}),
        rollback_on_failure=data.get("rollback_on_failure", True),
    )

    for step_data in data.get("steps", []):
        if not isinstance(step_data, dict):
            continue
        step_type = step_data.get("type", "custom")
        try:
            st = StepType(step_type)
        except ValueError:
            st = StepType.CUSTOM

        step = Step(
            type=st,
            name=step_data.get("name", ""),
            object_type=step_data.get("object_type", ""),
            object_name=step_data.get("object_name", ""),
            package=step_data.get("package", ""),
            transport=step_data.get("transport", wf.variables.get("transport", "")),
            source=step_data.get("source", ""),
            search=step_data.get("search", ""),
            replace=step_data.get("replace", ""),
            description=step_data.get("description", ""),
            method=step_data.get("method", ""),
            activate=step_data.get("activate", True),
            parameters=step_data.get("parameters", {}),
            continue_on_error=step_data.get("continue_on_error", False),
            condition=step_data.get("condition", ""),
        )
        wf.steps.append(step)

    return wf


def serialize_workflow(workflow: Workflow) -> str:
    """Serialize a Workflow object back to YAML."""
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required")

    data: dict[str, Any] = {
        "name": workflow.name,
        "description": workflow.description,
        "version": workflow.version,
    }
    if workflow.variables:
        data["variables"] = workflow.variables
    data["rollback_on_failure"] = workflow.rollback_on_failure

    steps = []
    for step in workflow.steps:
        step_dict: dict[str, Any] = {"type": step.type.value}
        if step.name:
            step_dict["name"] = step.name
        if step.object_type:
            step_dict["object_type"] = step.object_type
        if step.object_name:
            step_dict["object_name"] = step.object_name
        if step.package:
            step_dict["package"] = step.package
        if step.transport:
            step_dict["transport"] = step.transport
        if step.source:
            step_dict["source"] = step.source
        if step.search:
            step_dict["search"] = step.search
        if step.replace:
            step_dict["replace"] = step.replace
        if step.description:
            step_dict["description"] = step.description
        if step.method:
            step_dict["method"] = step.method
        if not step.activate:
            step_dict["activate"] = False
        if step.parameters:
            step_dict["parameters"] = step.parameters
        if step.continue_on_error:
            step_dict["continue_on_error"] = True
        if step.condition:
            step_dict["condition"] = step.condition
        steps.append(step_dict)

    data["steps"] = steps
    return yaml.dump(data, default_flow_style=False, sort_keys=False)
