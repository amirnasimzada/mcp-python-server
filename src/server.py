from mcp.server.fastmcp import FastMCP

mcp = FastMCP("custom-python-mcp")


@mcp.tool()
def healthcheck() -> str:
    """Simple health check."""
    return "ok"


@mcp.tool()
def echo(text: str) -> str:
    """Echo back text."""
    return text


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


if __name__ == "__main__":
    mcp.run()
