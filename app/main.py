import os
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from jwt import PyJWKClient
from pydantic import BaseModel, Field

APP_NAME = os.getenv("APP_NAME", "custom-python-mcp")
APP_VERSION = os.getenv("APP_VERSION", "1.1.0")
OIDC_ISSUER = os.getenv("OIDC_ISSUER", "")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "")
OIDC_JWKS_URI = os.getenv("OIDC_JWKS_URI", "")
OAUTH_AUTHORIZATION_SERVER = os.getenv("OAUTH_AUTHORIZATION_SERVER", OIDC_ISSUER)
REQUIRE_HTTPS_METADATA = os.getenv("REQUIRE_HTTPS_METADATA", "false").lower() == "true"

app = FastAPI(title=APP_NAME, version=APP_VERSION)


class ToolRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel):
    content: List[Dict[str, Any]]


TOOL_POLICIES: Dict[str, Dict[str, Set[str]]] = {
    "healthcheck": {"scopes": set(), "groups": set()},
    "echo": {"scopes": {"mcp:tools:echo"}, "groups": {"engineering", "security-admin"}},
    "add": {"scopes": {"mcp:tools:add"}, "groups": {"engineering", "security-admin"}},
    "list_findings": {"scopes": {"mcp:tools:list_findings"}, "groups": {"security-readonly", "security-admin"}},
    "close_finding": {"scopes": {"mcp:tools:close_finding"}, "groups": {"security-admin"}},
}


@lru_cache(maxsize=1)
def get_jwks_client() -> PyJWKClient:
    jwks_uri = OIDC_JWKS_URI.strip()
    if not jwks_uri:
        if not OIDC_ISSUER.strip():
            raise RuntimeError("OIDC_ISSUER or OIDC_JWKS_URI must be set")
        jwks_uri = OIDC_ISSUER.rstrip("/") + "/v1/keys"
    return PyJWKClient(jwks_uri)


def _parse_space_delimited_claim(value: Any) -> Set[str]:
    if isinstance(value, list):
        return {str(v) for v in value}
    if isinstance(value, str):
        return {v for v in value.split() if v}
    return set()


def _parse_groups(claims: Dict[str, Any]) -> Set[str]:
    groups = claims.get("groups")
    if isinstance(groups, list):
        return {str(v) for v in groups}
    return set()


def _validate_https(request: Request) -> None:
    if REQUIRE_HTTPS_METADATA and request.url.scheme != "https":
        raise HTTPException(status_code=400, detail="https_required")


def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_token")

    token = authorization[7:]
    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=OIDC_AUDIENCE or None,
            issuer=OIDC_ISSUER or None,
            options={
                "verify_aud": bool(OIDC_AUDIENCE),
                "verify_iss": bool(OIDC_ISSUER),
            },
        )
        return claims
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid_token: {exc}") from exc


def authorize_tool(tool_name: str, claims: Dict[str, Any]) -> None:
    policy = TOOL_POLICIES.get(tool_name)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown_tool")

    if tool_name == "healthcheck":
        return

    token_scopes = _parse_space_delimited_claim(claims.get("scp") or claims.get("scope"))
    token_groups = _parse_groups(claims)

    if policy["scopes"].intersection(token_scopes) or policy["groups"].intersection(token_groups):
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


def text_response(text: str) -> ToolResponse:
    return ToolResponse(content=[{"type": "text", "text": text}])


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {"ok": True, "app": APP_NAME, "version": APP_VERSION, "ts": int(time.time())}


@app.get("/.well-known/oauth-protected-resource")
def oauth_protected_resource(request: Request) -> Dict[str, Any]:
    _validate_https(request)
    resource = str(request.base_url).rstrip("/")
    auth_server = OAUTH_AUTHORIZATION_SERVER.rstrip("/") if OAUTH_AUTHORIZATION_SERVER else ""
    return {
        "resource": resource,
        "authorization_servers": [auth_server] if auth_server else [],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{resource}/docs",
    }


@app.get("/mcp/tools")
def list_tools(claims: Dict[str, Any] = Depends(verify_bearer_token)) -> Dict[str, Any]:
    visible = []
    for tool_name in TOOL_POLICIES:
        try:
            authorize_tool(tool_name, claims)
            visible.append(
                {
                    "name": tool_name,
                    "description": {
                        "healthcheck": "Returns service health",
                        "echo": "Echoes back the provided text",
                        "add": "Adds two numbers",
                        "list_findings": "Lists mock security findings",
                        "close_finding": "Closes a mock finding by id",
                    }[tool_name],
                }
            )
        except HTTPException:
            continue
    return {"tools": visible}


@app.post("/mcp/tools/{tool_name}", response_model=ToolResponse)
def invoke_tool(tool_name: str, payload: ToolRequest, claims: Dict[str, Any] = Depends(verify_bearer_token)) -> ToolResponse:
    authorize_tool(tool_name, claims)
    args = payload.arguments or {}

    if tool_name == "healthcheck":
        return text_response("ok")
    if tool_name == "echo":
        return text_response(str(args.get("text", "")))
    if tool_name == "add":
        a = float(args.get("a", 0))
        b = float(args.get("b", 0))
        return text_response(str(a + b))
    if tool_name == "list_findings":
        tenant = claims.get("tenant", "default")
        return ToolResponse(
            content=[
                {
                    "type": "json",
                    "json": {
                        "tenant": tenant,
                        "findings": [
                            {"id": "F-1001", "severity": "high", "status": "open"},
                            {"id": "F-1002", "severity": "medium", "status": "open"},
                        ],
                    },
                }
            ]
        )
    if tool_name == "close_finding":
        finding_id = str(args.get("finding_id", ""))
        if not finding_id:
            raise HTTPException(status_code=400, detail="finding_id_required")
        return text_response(f"finding {finding_id} closed")

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown_tool")
