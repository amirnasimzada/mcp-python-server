# Python Enterprise MCP Tool Server

This repo upgrades the original `mcp-python-server` starter into an **enterprise-style MCP tool server** with:

- FastAPI HTTP service
- OAuth/JWT bearer token validation
- JWKS-based signature verification
- per-tool RBAC / scope checks
- Protected Resource Metadata endpoint
- Dockerfile + GHCR publishing workflow

## Repo layout

```text
mcp-python-server/
├─ app/
│  └─ main.py
├─ .github/workflows/publish.yml
├─ .dockerignore
├─ .env.example
├─ Dockerfile
├─ README.md
└─ requirements.txt
```

## Tools included

- `healthcheck`
- `echo`
- `add`
- `list_findings`
- `close_finding`

## Default policy model

| Tool | Allowed by default |
|---|---|
| `healthcheck` | any valid token |
| `echo` | `mcp:tools:echo` scope or `engineering` / `security-admin` group |
| `add` | `mcp:tools:add` scope or `engineering` / `security-admin` group |
| `list_findings` | `mcp:tools:list_findings` scope or `security-readonly` / `security-admin` group |
| `close_finding` | `mcp:tools:close_finding` scope or `security-admin` group |

Edit `TOOL_POLICIES` in `app/main.py` to match your environment.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

## Docker run

```bash
docker build -t mcp-python-server .
docker run --rm -p 8080:8080 \
  --env-file .env \
  mcp-python-server
```

## Useful endpoints

Health:

```bash
curl http://localhost:8080/healthz
```

Protected resource metadata:

```bash
curl http://localhost:8080/.well-known/oauth-protected-resource
```

List authorized tools:

```bash
curl http://localhost:8080/mcp/tools \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Invoke echo:

```bash
curl -X POST http://localhost:8080/mcp/tools/echo \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"arguments":{"text":"hello"}}'
```

Invoke add:

```bash
curl -X POST http://localhost:8080/mcp/tools/add \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"arguments":{"a":2,"b":3}}'
```

## GitHub / GHCR

Push to `main` or tag with `v1.0.0` style tags. The workflow publishes to:

```text
ghcr.io/<OWNER>/<REPO>:latest
```

## Notes

- This is an enterprise-ready starter, not a full production platform.
- For production, put it behind your standard ingress / WAF / API gateway.
- Prefer validating JWTs at the gateway **and** in the app.
- Keep downstream credentials in your secret manager, not in client requests.
