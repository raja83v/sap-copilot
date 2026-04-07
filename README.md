# SAP Copilot

SAP Copilot is a multi-package workspace for AI-assisted SAP development using MCP tools, a Python gateway, and web dashboards.

## Repository Structure

- `abap-adt-mcp/`: Python MCP server for SAP ABAP ADT tooling
- `apps/gateway/`: Python gateway and orchestration layer
- `apps/web/`: Main frontend application (Vite + React)
- `convex/`: Convex backend functions and schema
- `convex-dashboard/`: Dashboard UI for Convex data inspection
- `packages/shared/`: Shared package(s) for cross-app code
- `docs/`: Project documentation and technical specifications

## Prerequisites

- Node.js 20+
- pnpm 9+
- Python 3.11+

## Quick Start

Install JS dependencies:

```bash
pnpm install
```

Run the main development workflow:

```bash
pnpm dev
```

Run individual services:

```bash
pnpm dev:web
pnpm dev:convex
pnpm dev:gateway
pnpm dev:dashboard
```

## Build

```bash
pnpm build
```

## Notes

- Local and generated artifacts are excluded via `.gitignore`.
- Test files are intentionally excluded from this repository push.
- Keep secrets in `.env.local` and never commit credentials.
