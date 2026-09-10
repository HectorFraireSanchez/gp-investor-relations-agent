from mcp.server import MCPServer

import domain


mcp = MCPServer("Northstar Investor Operations")


@mcp.tool()
def find_investor(name: str) -> dict | None:
    """Find an investor by name."""
    return domain.find_investor(name)


@mcp.tool()
def get_positions(investor_id: str) -> list[dict]:
    """Get an investor's fund positions."""
    return domain.get_positions(investor_id)


@mcp.tool()
def get_capital_calls(investor_id: str) -> list[dict]:
    """Get an investor's capital calls."""
    return domain.get_capital_calls(investor_id)


if __name__ == "__main__":
    mcp.run()