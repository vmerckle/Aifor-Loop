"""
Simple script demonstrating computer control with Claude using the computer use beta.
"""

import asyncio
import os
from typing import Callable

from anthropic import Anthropic
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaMessageParam,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
)

from dotenv import load_dotenv

from tools.bash import BashTool
from tools.computer import ComputerTool  
from tools.edit import EditTool
from tools.collection import ToolCollection
from tools.base import ToolResult

COMPUTER_USE_BETA_FLAG = "computer-use-2024-10-22"
SYSTEM_PROMPT = """You are helping control a computer by analyzing screenshots and suggesting specific actions.
You can use tools to interact with the computer and see the results."""

async def sampling_loop(
    *,
    messages: list[BetaMessageParam],
    output_callback: Callable[[BetaContentBlockParam], None] | None = None,
    tool_output_callback: Callable[[ToolResult, str], None] | None = None,
    api_key: str,
) -> list[BetaMessageParam]:
    """Run the agent sampling loop with the newest message"""
    
    tool_collection = ToolCollection(
        ComputerTool(),
        BashTool(),
        EditTool(),
    )

    client = Anthropic(api_key=api_key)
    
    while True:
        response = await client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=4096,
            messages=messages,
            system=SYSTEM_PROMPT,
            tools=tool_collection.to_params(),
            beta={"computer-use": True},
        )

        response_params = _response_to_params(response)
        messages.append(
            {
                "role": "assistant",
                "content": response_params,
            }
        )

        if output_callback:
            for content_block in response_params:
                output_callback(content_block)

        tool_result_content: list[BetaToolResultBlockParam] = []
        for content_block in response_params:
            if content_block["type"] == "tool_use":
                result = await tool_collection.run(
                    name=content_block["name"],
                    tool_input=content_block["input"],
                )
                tool_result_content.append(
                    _make_api_tool_result(result, content_block["id"])
                )
                if tool_output_callback:
                    tool_output_callback(result, content_block["id"])

        if not tool_result_content:
            return messages

        messages.append({"content": tool_result_content, "role": "user"})

def _response_to_params(response) -> list[BetaTextBlockParam]:
    """Convert API response to message params"""
    return [
        {"type": "text", "text": block.text} if block.type == "text" else block.model_dump()
        for block in response.content
    ]

def _make_api_tool_result(result: ToolResult, tool_use_id: str) -> BetaToolResultBlockParam:
    """Convert a tool result to API params"""
    tool_result_content: list[BetaTextBlockParam] = []
    is_error = False
    
    if result.error:
        is_error = True
        tool_result_content.append({"type": "text", "text": result.error})
    elif result.output:
        tool_result_content.append({"type": "text", "text": result.output})
        
    if result.base64_image:
        tool_result_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": result.base64_image
            }
        })
        
    return {
        "type": "tool_result",
        "content": tool_result_content,
        "tool_use_id": tool_use_id,
        "is_error": is_error,
    }

async def main():
    """Main entry point"""
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Please set ANTHROPIC_API_KEY environment variable")

    messages: list[BetaMessageParam] = [
        {
            "role": "user", 
            "content": [
                {
                    "type": "text",
                    "text": "Take a screenshot and tell me what you see."
                }
            ]
        }
    ]

    def print_output(content: BetaContentBlockParam):
        if content["type"] == "text":
            print(f"Assistant: {content['text']}")
        elif content["type"] == "tool_use":
            print(f"Tool use: {content['name']}")

    def print_tool_result(result: ToolResult, _: str):
        if result.error:
            print(f"Tool error: {result.error}")
        elif result.output:
            print(f"Tool output: {result.output}")

    await sampling_loop(
        messages=messages,
        output_callback=print_output,
        tool_output_callback=print_tool_result,
        api_key=api_key,
    )

if __name__ == "__main__":
    asyncio.run(main())
