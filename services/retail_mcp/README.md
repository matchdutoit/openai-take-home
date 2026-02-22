# RetailOps MCP

`retail_mcp` is an MCP server built with FastMCP. It exposes:

- READ tools over `/docs/knowledge` markdown:
  - `search(query)`
  - `fetch(id)`
- ACTION tools that proxy to RetailCore:
  - `inventory_lookup`
  - `reserve_item`
  - `create_transfer`
  - `create_ticket`

## Run with Docker Compose

From the repository root:

```bash
python3 scripts/generate_demo_pack.py
docker compose up --build retailcore retail_mcp
```

Services:

- RetailCore API: `http://localhost:8080`
- RetailOps MCP (HTTP transport): `http://localhost:8081/mcp`

For ACTION tools, include `X-DEMO-ROLE: associate|merch|support` on MCP requests so role is propagated to RetailCore.

## Golden Path Script

With services running:

```bash
python3 scripts/run_golden_path.py
```

This prints JSON outputs for:

1. Hero SKU inventory lookup
2. Reserve action (confirmed)
3. Merch transfer (confirmed)
4. Support ticket creation
