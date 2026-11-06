import asyncio

from mcp_server.server import server


def test_mcp_tools_registered():
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert {
        "codex_search",
        "storyboard_save",
        "prompt_compose",
        "generate_page",
        "gallery_list",
        "task_create",
        "task_get",
        "task_generate",
    } <= names
