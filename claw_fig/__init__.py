from __future__ import annotations
from typing import TYPE_CHECKING
import subprocess
import json
from shared.config import settings
from .models import FigmaCreateRequest, FigmaCreateResult

if TYPE_CHECKING:
    from mcp import Client


class FigmaMCPClient:
    def __init__(self, api_token: str | None = None):
        self.api_token = api_token or settings.figma_api_token
        self._process: subprocess.Popen | None = None
        self._client: Client | None = None

    async def _get_client(self):
        if self._client is None:
            from mcp import Client

            self._client = Client(
                server_name="figma",
                server_url="https://mcp.figma.com/mcp",
            )
        return self._client

    async def add_file(self, file_url: str) -> dict:
        client = await self._get_client()
        return await client.call_tool("add_figma_file", {"file_url": file_url})

    async def get_design_context(
        self, file_url: str, format: str = "react-tsx"
    ) -> dict:
        client = await self._get_client()
        return await client.call_tool(
            "get_design_context",
            {
                "file_url": file_url,
                "format": format,
            },
        )

    async def extract_images(self, file_url: str, node_ids: list[str]) -> dict:
        client = await self._get_client()
        return await client.call_tool(
            "get_images",
            {
                "file_url": file_url,
                "node_ids": node_ids,
            },
        )


class FigmaMCPStdioClient:
    def __init__(self, api_token: str | None = None):
        self.api_token = api_token or settings.figma_api_token
        self._process: subprocess.Popen | None = None

    def _start_server(self):
        if self._process is None:
            self._process = subprocess.Popen(
                [
                    "npx",
                    "-y",
                    "figma-developer-mcp",
                    "--figma-api-key",
                    self.api_token,
                    "--stdio",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={"FIGMA_API_KEY": self.api_token},
            )
        return self._process

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        self._start_server()
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        self._process.stdin.write(json.dumps(request).encode() + b"\n")
        self._process.stdin.flush()
        response = self._process.stdout.readline()
        return json.loads(response)

    async def close(self):
        if self._process:
            self._process.terminate()
            self._process = None


async def build_figma_design_system(
    analysis_result: dict,
    project_name: str,
    figma_file_url: str | None = None,
) -> FigmaCreateResult:
    if figma_file_url:
        client = FigmaMCPClient()
        await client.add_file(figma_file_url)
        design_context = await client.get_design_context(figma_file_url)
    else:
        design_context = {
            "tokens": analysis_result.get("color_palette", {}),
            "typography": analysis_result.get("typography_scale", {}),
            "components": analysis_result.get("components", []),
        }

    tokens = analysis_result.get("color_palette", {})
    components = analysis_result.get("components", [])

    color_count = sum(len(colors) for colors in tokens.values())
    component_count = len(components)

    return FigmaCreateResult(
        file_key=project_name,
        file_url=figma_file_url or f"https://www.figma.com/design/{project_name}",
        styles_created=color_count,
        components_created=component_count,
    )


async def export_figma_to_code(
    file_url: str,
    format: str = "react-tsx",
) -> str:
    client = FigmaMCPClient()
    await client.add_file(file_url)
    result = await client.get_design_context(file_url, format)
    return result.get("code", "")
