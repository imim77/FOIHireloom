import unittest

from fastmcp import Client

from FOIHireloom.api.mcp_server import McpServer


class McpServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_connects_without_registered_tools(self) -> None:
        async with Client(McpServer().server) as client:
            tools = await client.list_tools()
            self.assertEqual(tools, [])
