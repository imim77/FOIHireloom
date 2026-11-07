import unittest
from contextlib import asynccontextmanager

from fastmcp import Client, Context, FastMCP
from fastmcp.exceptions import ToolError

from FOIHireloom.api.tool_provider import ServiceToolGroup, tool_arguments
from FOIHireloom.exceptions import InvalidJobSearchError, NotFoundError, PersistenceError


class EchoTools(ServiceToolGroup[dict]):
    _service_key = "echo"
    _caller_errors = (InvalidJobSearchError,)
    _unavailable_message = "Echo data is temporarily unavailable."

    def register(self, server: FastMCP) -> None:
        self._add_tool(server, self.echo)

    async def echo(self, ctx: Context, word: str, shout: bool = False) -> dict:
        """Return the arguments, or raise the service's error."""
        arguments = tool_arguments(locals(), "shout")
        if error := self._service(ctx).get("error"):
            await self._call(self._fail(error))
        return arguments

    @staticmethod
    async def _fail(error: Exception) -> None:
        raise error


class ServiceToolGroupTests(unittest.IsolatedAsyncioTestCase):
    def server(self, error: Exception | None = None) -> FastMCP:
        @asynccontextmanager
        async def lifespan(server: FastMCP):
            yield {"echo": {"error": error}}

        server = FastMCP("test", lifespan=lifespan, mask_error_details=True)
        EchoTools().register(server)
        return server

    async def test_tools_are_read_only_and_receive_their_arguments_without_self_ctx_or_omitted_ones(self) -> None:
        async with Client(self.server()) as client:
            tool = (await client.list_tools())[0]
            result = await client.call_tool("echo", {"word": "kuhar", "shout": True})
        self.assertTrue(tool.annotations.readOnlyHint)
        self.assertEqual(result.structured_content, {"word": "kuhar"})

    async def test_caller_errors_keep_details_and_database_errors_hide_them(self) -> None:
        cases = ((InvalidJobSearchError("Query has no words."), "Query has no words."),
                 (PersistenceError("connection refused"), "Echo data is temporarily unavailable."))
        for error, message in cases:
            with self.subTest(error=type(error).__name__):
                async with Client(self.server(error)) as client:
                    with self.assertRaisesRegex(ToolError, f"^{message}$"):
                        await client.call_tool("echo", {"word": "kuhar"})

    async def test_other_errors_stay_masked(self) -> None:
        async with Client(self.server(NotFoundError("job", "7"))) as client:
            with self.assertRaises(ToolError) as raised:
                await client.call_tool("echo", {"word": "kuhar"})
        self.assertNotIn("Job 7", str(raised.exception))
