# CLAUDE.md — VSP Python MCP Server

## Project Overview

VSP (Vibing Steampunk Python) is a Python MCP server that provides ~99 tools for SAP ABAP development via the ADT REST API. It's a Python reimplementation of the original Go-based VSP server.

## Architecture

### Layer Stack
```
CLI (click)
  → VspServer (server.py) — MCP protocol + tool registration
    → Handlers (handlers/*.py) — tool implementations
      → ADT Client (adt/client.py) — high-level ABAP operations
        → HTTP Transport (adt/http.py) — CSRF, sessions, cookies
          → SAP ADT REST API
```

### Key Modules
- **`src/vsp/config.py`** — Config dataclass, enums, operation codes
- **`src/vsp/cli.py`** — Click CLI with ~25 options
- **`src/vsp/server.py`** — MCP server orchestrator, tool group management
- **`src/vsp/adt/http.py`** — httpx async transport, CSRF token lifecycle
- **`src/vsp/adt/client.py`** — ADT read operations (source, packages, metadata)
- **`src/vsp/adt/crud.py`** — Lock/unlock/create/delete/update
- **`src/vsp/adt/devtools.py`** — Syntax check, activate, unit tests, ATC
- **`src/vsp/adt/codeintel.py`** — Find definition/references, completion
- **`src/vsp/adt/workflows.py`** — High-level write/edit/compare/grep/clone
- **`src/vsp/adt/safety.py`** — Operation/package/transport guards
- **`src/vsp/adt/features.py`** — Feature detection with caching
- **`src/vsp/adt/debugger.py`** — ABAP debugger session management
- **`src/vsp/adt/websocket.py`** — WebSocket client for ZADT_VSP
- **`src/vsp/adt/xml_types.py`** — ADT XML dataclasses and builders
- **`src/vsp/dsl/`** — YAML workflow definitions and executor
- **`src/vsp/cache/`** — Memory and SQLite async cache
- **`src/vsp/handlers/`** — 15 handler modules registering MCP tools

### Handler Modules
| Module | Tools | Description |
|--------|-------|-------------|
| `read.py` | GetSource, GetClassInclude, GetPackage, GetTable, etc. | Source code reading |
| `search.py` | SearchObject, GrepObject, GrepPackage | Object and code search |
| `system.py` | GetConnectionInfo, GetFeatures, GetAbapHelp, etc. | System information |
| `crud.py` | WriteSource, EditSource, CreateObject, DeleteObject, etc. | CRUD operations |
| `devtools.py` | SyntaxCheck, Activate, RunUnitTests, RunATCCheck, etc. | Dev tools |
| `codeintel.py` | FindDefinition, FindReferences, CodeCompletion, etc. | Code intelligence |
| `diagnostics.py` | ListDumps, GetDump, ListTraces, SQL traces | Runtime diagnostics |
| `transport.py` | ListTransports, CreateTransport, ReleaseTransport | CTS |
| `analysis.py` | GetCallGraph, GetCallersOf, GetCalleesOf | Code analysis |
| `debug.py` | SetBreakpoint, DebuggerStep, DebuggerGetVariables | ABAP debugger |
| `ui5.py` | UI5ListApps, UI5GetApp, UI5UploadFile | BSP/UI5 repository |
| `git.py` | GitListRepos, GitPull, GitPush, GitExport | abapGit |
| `report.py` | RunReport, RunReportAsync, RFCCall | Report execution |
| `install.py` | InstallZADTVSP, ListDependencies | Installation helpers |
| `amdp.py` | AMDPDebuggerStart, AMDPGetSource | AMDP/HANA |

## Tech Stack
- Python 3.11+
- `mcp` (Anthropic official SDK)
- `httpx[http2]` — async HTTP client
- `click` — CLI framework
- `lxml` — XML parsing
- `pyyaml` — DSL workflows
- `websockets` — ZADT_VSP communication
- `aiosqlite` — persistent cache
- `pytest` + `pytest-asyncio` — testing

## Safety System

Operations are gated by single-character codes:
- `R` Read, `S` Search, `Q` Query, `F` Free SQL
- `C` Create, `U` Update, `D` Delete, `A` Activate
- `T` Test, `L` Lock, `I` Intelligence, `W` Workflow
- `X` Transport, `B` Debug, `N` Install

Safety config supports: read-only mode, allowed/disallowed ops, package wildcards, transport allowlists.

## CSRF Token Flow
1. HEAD `/sap/bc/adt/core/discovery` with `x-csrf-token: Fetch`
2. Store response token + session cookies
3. Include token in all mutating requests
4. On 403 → refresh token automatically
5. On 400 with `ICMENOSESSION` → full session recovery

## Running
```bash
vsp --url https://sap.example.com --user DEV --password secret --client 100
```

## Testing
```bash
pytest tests/unit/          # Unit tests (no SAP connection)
pytest tests/integration/   # Integration tests (needs SAP)
```
