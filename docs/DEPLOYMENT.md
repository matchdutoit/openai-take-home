# Deployment Guide (Render)

This project includes two services:

- `retailcore` (FastAPI, port `8080`)
- `retail_mcp` (FastMCP, port `8081`)

For ChatGPT integration, deploy `retail_mcp` as a Render **Web Service**.

## 1) Prerequisites

- Repo pushed to GitHub/GitLab.
- Render account.
- `retailcore` reachable from `retail_mcp` (same Render private network or public URL).

## 2) Create `retail_mcp` Web Service on Render

1. In Render, click **New +** -> **Web Service**.
2. Connect your repo.
3. Configure:
   - Runtime: `Docker`
   - Dockerfile path: `services/retail_mcp/Dockerfile`
   - Service name: `retail-mcp`
   - Region: same region as `retailcore`
   - Render note: for Docker services, the UI may not show a separate Port field.

## 3) Environment Variables

Set these in Render:

- `PORT=8081` (Render-routing port)
- `RETAILCORE_BASE_URL`
  - Example private URL: `http://retailcore:8080`
  - Example public URL: `https://retailcore.onrender.com`
- `RETAIL_MCP_DATA_DIR=/app/data`
- `RETAIL_MCP_DOCS_DIR=/app/docs/knowledge`
- `FASTMCP_TRANSPORT=http`
- `FASTMCP_HOST=0.0.0.0`
- `FASTMCP_PORT=8081` (optional if `PORT` is already set)
- `FASTMCP_PATH=/mcp`

## 4) Health Check Endpoint

`retail_mcp` exposes:

- `GET /health` -> `{"status":"ok","service":"retail_mcp"}`

Set Render health check path to:

- `/health`

## 5) HTTPS Requirement (Important)

- Use the Render-generated `https://...` URL for any ChatGPT/UI-facing MCP endpoint.
- Do not use plaintext `http://` for public ChatGPT connections.
- If `retailcore` is also public, prefer an `https://` `RETAILCORE_BASE_URL`.

## 6) Verify Deployment

After deploy:

1. Open `https://<your-retail-mcp-domain>/health` and confirm status `ok`.
2. Confirm MCP endpoint is reachable at `https://<your-retail-mcp-domain>/mcp`.
3. In ChatGPT connector/app setup, use the HTTPS MCP URL.
