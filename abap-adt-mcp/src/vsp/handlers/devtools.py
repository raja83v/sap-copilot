"""DevTools tool handlers — SyntaxCheck, Activate, UnitTests, ATC, PrettyPrint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_READ, OP_WRITE

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_devtools_tools(server: VspServer) -> None:
    """Register development tools MCP tools."""

    @server.mcp.tool(
        name="SyntaxCheck",
        description="Run ABAP syntax check on an object. Returns list of errors/warnings with line numbers.",
    )
    async def syntax_check(name: str, object_type: str = "") -> str:
        try:
            server.check_safety(OP_READ)
            from vsp.adt.crud import OBJECT_URI_PATHS
            from urllib.parse import quote
            obj_type = object_type.upper() or "PROG"
            path_template = OBJECT_URI_PATHS.get(obj_type)
            if not path_template:
                return f"Error: unsupported object type '{obj_type}'"
            uri = path_template.format(name=quote(name.upper()))
            raw_xml, messages = await server.devtools.syntax_check(uri)
            if not messages:
                if raw_xml.strip():
                    return f"Syntax check passed — no issues found.\n[DEBUG raw SAP response]:\n{raw_xml}"
                return "Syntax check passed — no issues found."
            lines = [f"Syntax check found {len(messages)} issues:"]
            for m in messages:
                lines.append(f"  [{m.type}] Line {m.line}: {m.text}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="Activate",
        description="Activate (compile) an ABAP object. Must be called after source changes.",
    )
    async def activate(name: str, object_type: str = "") -> str:
        try:
            server.check_safety(OP_WRITE)
            from vsp.adt.crud import OBJECT_URI_PATHS
            from urllib.parse import quote
            obj_type = object_type.upper() or "PROG"
            path_template = OBJECT_URI_PATHS.get(obj_type)
            if not path_template:
                return f"Error: unsupported object type '{obj_type}'"
            uri = path_template.format(name=quote(name.upper()))
            result, raw_body = await server.devtools.activate(uri, obj_type, name.upper())
            if not result:
                if raw_body.strip():
                    return f"Successfully activated {name.upper()}.\n[SAP raw response]:\n{raw_body}"
                return f"Successfully activated {name.upper()}."
            return "\n".join(str(m) for m in result)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="ActivateList",
        description="Activate a list of objects at once. Provide objects as comma-separated 'type:name' pairs.",
    )
    async def activate_list(objects: str) -> str:
        try:
            server.check_safety(OP_WRITE)
            from vsp.adt.crud import OBJECT_URI_PATHS
            from urllib.parse import quote
            # Parse "CLAS:ZCL_MY_CLASS,PROG:ZTEST" format
            objs: list[tuple[str, str, str]] = []
            for item in objects.split(","):
                item = item.strip()
                if ":" in item:
                    t, n = item.split(":", 1)
                    ot = t.strip().upper()
                    nm = n.strip().upper()
                    path_template = OBJECT_URI_PATHS.get(ot)
                    if not path_template:
                        return f"Error: unsupported object type '{ot}'"
                    uri = path_template.format(name=quote(nm))
                    objs.append((uri, ot, nm))
            if not objs:
                return "Error: provide objects as 'TYPE:NAME' pairs separated by commas"
            result, raw_body = await server.devtools.activate_list(objs)
            if not result:
                if raw_body.strip():
                    return f"Successfully activated {len(objs)} object(s).\n[SAP raw response]:\n{raw_body}"
                return f"Successfully activated {len(objs)} object(s)."
            return "\n".join(str(m) for m in result)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="ActivatePackage",
        description="Activate all inactive objects in a package.",
    )
    async def activate_package(package: str) -> str:
        try:
            server.check_safety(OP_WRITE)
            result, raw_body = await server.devtools.activate_package(package)
            if not result:
                if raw_body.strip():
                    return f"Activated package {package}.\n[SAP raw response]:\n{raw_body}"
                return f"Activated package {package}."
            return "\n".join(str(m) for m in result)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetInactiveObjects",
        description="List all inactive (not yet activated) objects for the current user.",
    )
    async def get_inactive_objects() -> str:
        try:
            server.check_safety(OP_READ)
            objects = await server.devtools.get_inactive_objects()
            if not objects:
                return "No inactive objects."
            lines = [f"Inactive objects ({len(objects)}):"]
            for obj in objects:
                lines.append(f"  [{obj.get('type', '?')}] {obj.get('name', '?')}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="RunUnitTests",
        description="Execute ABAP Unit tests for an object. Returns pass/fail results per method.",
    )
    async def run_unit_tests(name: str, object_type: str = "") -> str:
        try:
            server.check_safety(OP_READ)
            result = await server.devtools.run_unit_tests(object_type, name)
            lines = [f"Unit Test Results for {name}:"]
            for cls in result.classes:
                lines.append(f"\n  Class: {cls.name}")
                for method in cls.methods:
                    status = "PASS" if method.passed else "FAIL"
                    lines.append(f"    [{status}] {method.name}")
                    for alert in method.alerts:
                        lines.append(f"      {alert.severity}: {alert.text}")
                        if alert.details:
                            lines.append(f"        {alert.details}")
            total = sum(len(c.methods) for c in result.classes)
            passed = sum(1 for c in result.classes for m in c.methods if m.passed)
            lines.append(f"\nTotal: {passed}/{total} passed")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="RunATCCheck",
        description="Run ATC (ABAP Test Cockpit) analysis on an object. Returns findings with priorities.",
    )
    async def run_atc_check(name: str, object_type: str = "", variant: str = "") -> str:
        try:
            server.check_safety(OP_READ)
            findings = await server.devtools.run_atc_check(object_type, name, variant=variant)
            if not findings:
                return "ATC check passed — no findings."
            lines = [f"ATC Findings ({len(findings)}):"]
            for f in findings:
                lines.append(f"  [{f.priority}] {f.check_title}: {f.message_title}")
                if f.location:
                    lines.append(f"    Location: {f.location}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetATCCustomizing",
        description="Get ATC check variant configuration.",
    )
    async def get_atc_customizing() -> str:
        try:
            server.check_safety(OP_READ)
            result = await server.devtools.get_atc_customizing()
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="PrettyPrint",
        description="Format ABAP source code using pretty printer. "
        "Returns the formatted source code.",
    )
    async def pretty_print(name: str, object_type: str = "") -> str:
        try:
            server.check_safety(OP_WRITE)
            result = await server.devtools.pretty_print(object_type, name)
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetPrettyPrinterSettings",
        description="Get current pretty printer settings (indentation, case conversion, etc.).",
    )
    async def get_pretty_printer_settings() -> str:
        try:
            server.check_safety(OP_READ)
            return await server.devtools.get_pretty_printer_settings()
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="SetPrettyPrinterSettings",
        description="Update pretty printer settings.",
    )
    async def set_pretty_printer_settings(settings_json: str) -> str:
        try:
            server.check_safety(OP_WRITE)
            import json
            settings = json.loads(settings_json)
            return await server.devtools.set_pretty_printer_settings(settings)
        except Exception as e:
            return f"Error: {e}"
