# VSP — Python MCP Server for SAP ABAP ADT

A Python reimplementation of the VSP (Vibing Steampunk) MCP server for SAP ABAP Development Tools (ADT).

## Features

- **~99 MCP tools** for complete SAP ABAP development via AI assistants
- Full async architecture (asyncio + httpx)
- SAP ADT REST API client with CSRF token management
- Safety controls (read-only mode, package restrictions, transport validation)
- Feature detection (abapGit, RAP, AMDP, UI5, HANA)
- YAML-based workflow DSL for multi-step operations
- In-memory and SQLite-backed caching
- WebSocket support for ZADT_VSP companion

## Quick Start

```bash
# Install
pip install -e .

# Configure
export SAP_URL=https://your-sap-system.example.com
export SAP_USER=YOUR_USER
export SAP_PASSWORD=YOUR_PASSWORD
export SAP_CLIENT=100

# Run
vsp
```

## Configuration

All configuration via environment variables or CLI flags:

| Variable | CLI Flag | Description |
|----------|----------|-------------|
| `SAP_URL` | `--url` | SAP system URL |
| `SAP_USER` | `--user` | SAP username |
| `SAP_PASSWORD` | `--password` | SAP password |
| `SAP_CLIENT` | `--client` | SAP client number |
| `SAP_LANGUAGE` | `--language` | Logon language (default: EN) |
| `VSP_MODE` | `--mode` | Tool mode: focused/expert |
| `VSP_INSECURE` | `--insecure` | Skip TLS verification |

See `env.example` for all options.

## Architecture

```
CLI (click) → MCP Server → Handlers → ADT Client → HTTP Transport → SAP
                              ↓
                         DSL Executor
                              ↓
                         Cache Layer
```

## Tool Groups

| Code | Group | Description |
|------|-------|-------------|
| - | core | Read, search, system info (always enabled) |
| - | crud | Create, update, delete objects |
| T | test | Unit tests, ATC checks |
| D | debug | ABAP debugger |
| C | cts | Transport management |
| G | git | abapGit integration |
| U | ui5 | UI5/BSP repository |
| R | reports | Report execution |
| I | install | Dependency installation |
| H | hana | AMDP debugging |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src tests

# Type check
mypy src
```

## License

MIT
