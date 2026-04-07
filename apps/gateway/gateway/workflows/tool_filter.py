"""Tool filtering — scope MCP tools per agent role.

Each agent sees only the tool categories relevant to its job.
Categories are the same keys used in packages/shared/src/constants.ts
(TOOL_TO_CATEGORY map).
"""

from __future__ import annotations

from typing import Any

from .state import AgentRole

# Maps each agent role to the set of tool categories it may use.
AGENT_TOOL_CATEGORIES: dict[AgentRole, set[str]] = {
    "planner": {"read", "search", "system", "codeintel", "analysis"},
    "clarifier": {"read", "search", "system"},
    "coder": {"crud", "read", "search", "codeintel", "report"},
    "reviewer": {"devtools", "read", "search", "codeintel", "analysis"},
    "tester": {"devtools", "read", "search", "diagnostics"},
    "activator": {"devtools", "transport", "read"},
    "analyzer": {"analysis", "diagnostics", "codeintel", "read", "search"},
    "documenter": {"read", "search", "codeintel"},
    "migrator": {"crud", "transport", "read", "search"},
}

# Mirrors packages/shared/src/constants.ts → TOOL_TO_CATEGORY
TOOL_TO_CATEGORY: dict[str, str] = {
    # Read
    "GetSource": "read", "GetClassInclude": "read", "GetClassInfo": "read",
    "GetPackage": "read", "GetTable": "read", "GetTableContents": "read",
    "RunQuery": "read", "GetFunctionGroup": "read", "GetMessages": "read",
    "GetCDSDependencies": "read", "GetProgram": "read", "GetClass": "read",
    "GetInterface": "read", "GetFunction": "read", "GetInclude": "read",
    "GetStructure": "read", "GetTransaction": "read", "GetTypeInfo": "read",
    # Search
    "SearchObject": "search", "GrepObject": "search", "GrepPackage": "search",
    # CRUD
    "LockObject": "crud", "UnlockObject": "crud", "CreateObject": "crud",
    "CreatePackage": "crud", "CreateTable": "crud", "DeleteObject": "crud",
    "WriteSource": "crud", "EditSource": "crud", "CompareSource": "crud",
    "CloneObject": "crud",
    # System
    "GetConnectionInfo": "system", "GetFeatures": "system",
    "GetAbapHelp": "system", "GetSystemInfo": "system",
    "GetInstalledComponents": "system", "GetServiceBinding": "system",
    # DevTools
    "SyntaxCheck": "devtools", "Activate": "devtools",
    "ActivateList": "devtools", "ActivatePackage": "devtools",
    "GetInactiveObjects": "devtools",
    "RunUnitTests": "devtools", "RunATCCheck": "devtools",
    "GetATCCustomizing": "devtools",
    "PrettyPrint": "devtools", "GetPrettyPrinterSettings": "devtools",
    "SetPrettyPrinterSettings": "devtools",
    # Transport
    "ListTransports": "transport", "GetTransport": "transport",
    "CreateTransport": "transport", "ReleaseTransport": "transport",
    "DeleteTransport": "transport", "AddToTransport": "transport",
    # Diagnostics
    "ListDumps": "diagnostics", "GetDump": "diagnostics",
    "ListTraces": "diagnostics", "GetTrace": "diagnostics",
    "GetTraceAnalysis": "diagnostics",
    "GetSQLTraceState": "diagnostics", "SetSQLTraceState": "diagnostics",
    "ListSQLTraces": "diagnostics",
    # CodeIntel
    "FindDefinition": "codeintel", "FindReferences": "codeintel",
    "CodeCompletion": "codeintel", "GetTypeHierarchy": "codeintel",
    "GetClassComponents": "codeintel", "GetUsageLocations": "codeintel",
    # Analysis
    "GetCallGraph": "analysis", "GetObjectStructure": "analysis",
    "GetCallersOf": "analysis", "GetCalleesOf": "analysis",
    "AnalyzeCallGraph": "analysis", "GetObjectExplorer": "analysis",
    # Debug
    "SetBreakpoint": "debug", "GetBreakpoints": "debug",
    "DeleteBreakpoint": "debug", "DeleteAllBreakpoints": "debug",
    "DebuggerListen": "debug", "DebuggerStep": "debug",
    "DebuggerGetStack": "debug", "DebuggerGetVariables": "debug",
    "DebuggerSetVariable": "debug", "DebuggerGetSource": "debug",
    "DebuggerDetach": "debug",
    # Report
    "RunReport": "report", "RunReportAsync": "report",
    "GetAsyncResult": "report", "GetVariants": "report",
    "GetReportOutput": "report", "RFCCall": "report",
    # Git
    "GitListRepos": "git", "GitGetRepo": "git", "GitExport": "git",
    "GitPull": "git", "GitStage": "git", "GitPush": "git", "GitLink": "git",
    # UI5
    "UI5ListApps": "ui5", "UI5GetApp": "ui5", "UI5GetFileContent": "ui5",
    "UI5UploadFile": "ui5", "UI5DeleteFile": "ui5", "UI5CreateApp": "ui5",
    # AMDP
    "AMDPGetProcedures": "amdp", "AMDPGetSource": "amdp",
    "AMDPDebuggerStart": "amdp", "AMDPDebuggerResume": "amdp",
    "AMDPDebuggerStep": "amdp", "AMDPDebuggerGetVariables": "amdp",
    "AMDPDebuggerStop": "amdp", "AMDPSetBreakpoint": "amdp",
    # Install
    "InstallZADTVSP": "install", "InstallAbapGit": "install",
    "ListDependencies": "install", "GetServerVersion": "install",
}


# Extra tools granted to the coder beyond its category set.
# SyntaxCheck lives in "devtools" but the coder needs it to verify code.
_CODER_EXTRA_TOOLS = {"SyntaxCheck"}


def filter_tools_for_agent(
    all_tools: list[dict[str, Any]],
    role: AgentRole,
) -> list[dict[str, Any]]:
    """Return only the MCP tools allowed for the given agent role."""
    allowed_categories = AGENT_TOOL_CATEGORIES.get(role, set())
    return [
        t for t in all_tools
        if TOOL_TO_CATEGORY.get(t.get("name", ""), "") in allowed_categories
        or (role == "coder" and t.get("name", "") in _CODER_EXTRA_TOOLS)
    ]
