"""DSL workflow executor — runs parsed workflows against an ADT client."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from vsp.dsl.types import (
    Step,
    StepResult,
    StepType,
    Workflow,
    WorkflowResult,
)

if TYPE_CHECKING:
    from vsp.server import VspServer

logger = logging.getLogger("vsp.dsl")


class WorkflowExecutor:
    """Executes DSL workflow definitions against a VspServer instance."""

    def __init__(self, server: VspServer):
        self.server = server

    async def run(self, workflow: Workflow) -> WorkflowResult:
        """Execute all steps in a workflow sequentially."""
        result = WorkflowResult(workflow=workflow, success=True)
        start = time.monotonic()

        # Resolve variables into step fields
        resolved_steps = self._resolve_variables(workflow)

        for step in resolved_steps:
            step_result = await self._execute_step(step)
            result.step_results.append(step_result)

            if not step_result.success:
                if step.continue_on_error:
                    logger.warning("Step '%s' failed (continuing): %s", step.name, step_result.error)
                else:
                    result.success = False
                    logger.error("Step '%s' failed: %s", step.name, step_result.error)
                    if workflow.rollback_on_failure:
                        logger.info("Workflow failed, rollback_on_failure is enabled")
                    break

        result.total_elapsed_ms = (time.monotonic() - start) * 1000
        return result

    async def _execute_step(self, step: Step) -> StepResult:
        """Execute a single step."""
        start = time.monotonic()
        try:
            output = await self._dispatch_step(step)
            elapsed = (time.monotonic() - start) * 1000
            return StepResult(step=step, success=True, output=output, elapsed_ms=elapsed)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return StepResult(step=step, success=False, error=str(e), elapsed_ms=elapsed)

    async def _dispatch_step(self, step: Step) -> str:
        """Route a step to the appropriate server method."""
        match step.type:
            case StepType.CREATE:
                await self.server.crud.create_object(
                    step.object_type,
                    step.object_name,
                    package=step.package,
                    description=step.description,
                    transport=step.transport,
                    source=step.source,
                )
                return f"Created {step.object_type} {step.object_name}"

            case StepType.WRITE:
                result = await self.server.workflows.write_source(
                    step.object_type,
                    step.object_name,
                    step.source,
                    method=step.method,
                    transport=step.transport,
                    activate=step.activate,
                )
                return result

            case StepType.EDIT:
                result = await self.server.workflows.edit_source(
                    step.object_type,
                    step.object_name,
                    search=step.search,
                    replace=step.replace,
                    method=step.method,
                    transport=step.transport,
                    activate=step.activate,
                )
                return result

            case StepType.DELETE:
                await self.server.crud.delete_object(
                    step.object_type,
                    step.object_name,
                    transport=step.transport,
                )
                return f"Deleted {step.object_type} {step.object_name}"

            case StepType.ACTIVATE:
                messages, _ = await self.server.devtools.activate(
                    step.object_type, step.object_name
                )
                return str(messages) if messages else "Activated."

            case StepType.TEST:
                result = await self.server.devtools.run_unit_tests(
                    step.object_type, step.object_name
                )
                total = sum(len(c.methods) for c in result.classes)
                passed = sum(1 for c in result.classes for m in c.methods if m.passed)
                if passed < total:
                    raise RuntimeError(f"Tests failed: {passed}/{total}")
                return f"Tests passed: {passed}/{total}"

            case StepType.ATC:
                findings = await self.server.devtools.run_atc_check(
                    step.object_type, step.object_name
                )
                if findings:
                    return f"ATC: {len(findings)} findings"
                return "ATC: no findings"

            case StepType.LOCK:
                handle = await self.server.crud.lock_object(
                    step.object_type, step.object_name
                )
                return f"Locked: {handle}"

            case StepType.UNLOCK:
                lock_handle = step.parameters.get("lock_handle", "")
                await self.server.crud.unlock_object(
                    step.object_type, step.object_name, lock_handle
                )
                return "Unlocked"

            case _:
                raise ValueError(f"Unknown step type: {step.type}")

    def _resolve_variables(self, workflow: Workflow) -> list[Step]:
        """Substitute workflow-level variables into step fields."""
        if not workflow.variables:
            return workflow.steps

        resolved = []
        for step in workflow.steps:
            # Simple string substitution for ${var_name} patterns
            import re

            def replace_var(val: str) -> str:
                def replacer(m: re.Match) -> str:
                    var_name = m.group(1)
                    return workflow.variables.get(var_name, m.group(0))
                return re.sub(r"\$\{(\w+)\}", replacer, val)

            new_step = Step(
                type=step.type,
                name=replace_var(step.name),
                object_type=replace_var(step.object_type),
                object_name=replace_var(step.object_name),
                package=replace_var(step.package),
                transport=replace_var(step.transport),
                source=replace_var(step.source),
                search=replace_var(step.search),
                replace=replace_var(step.replace),
                description=replace_var(step.description),
                method=replace_var(step.method),
                activate=step.activate,
                parameters=step.parameters,
                continue_on_error=step.continue_on_error,
                condition=replace_var(step.condition),
            )
            resolved.append(new_step)
        return resolved
