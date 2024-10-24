import asyncio
import platform
import base64
import os
import subprocess
import traceback
from datetime import datetime, timedelta
from enum import StrEnum
from functools import partial
from pathlib import PosixPath
from typing import cast

import httpx
from anthropic import RateLimitError
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaTextBlockParam,
)
from loop import (
    PROVIDER_TO_DEFAULT_MODEL_NAME,
    APIProvider,
    sampling_loop,
)


from tools.bash import BashTool
from tools.computer import ComputerTool  
from tools.edit import EditTool
from tools.collection import ToolCollection
from tools.base import ToolResult

from dotenv import load_dotenv

# Load system prompt
SYSTEM_PROMPT = f"You are are in control of a machine using {platform.machine()} architecture and running {platform.freedesktop_os_release()['NAME']}. Please don't delete anything unless asked three times."

class Sender(StrEnum):
    USER = "user"
    BOT = "assistant"
    TOOL = "tool"

async def main():
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    provider = APIProvider.ANTHROPIC
    model = PROVIDER_TO_DEFAULT_MODEL_NAME[provider]
    
    # provider_radio is provider
    # auth is not validated
    responses = {}
    tools = {}
    only_n_most_recent_images = 10
    hide_images = False

    # Load first message
    with open('prompt.txt', 'r') as f:
        first_message = f.read().strip()

    messages = [
        {
            "role": Sender.USER,
            "content": [BetaTextBlockParam(type="text", text=first_message)],
        }
    ]

    messages = await sampling_loop(
        system_prompt=SYSTEM_PROMPT,
        model=model,
        provider = provider,
        messages = messages,
        output_callback = partial(_render_message, Sender.BOT),
        tool_output_callback=partial(
            _tool_output_callback, tool_state=tools
        ),
        api_response_callback=partial(
            _api_response_callback,
            response_state=responses,
        ),
        api_key=api_key,
        only_n_most_recent_images=only_n_most_recent_images,
    )

    print(f"Printing {len(messages)} messages...\n")
    for message in messages:
        if isinstance(message["content"], str):
            print((message["role"], message["content"]))
        elif isinstance(message["content"], list):
            print(message["role"])
            for b in message["content"]:
                print(b)

def _api_response_callback(
    request: httpx.Request,
    response: httpx.Response | object | None,
    error: Exception | None,
    response_state: dict[str, tuple[httpx.Request, httpx.Response | object | None]],
):
    """
    Handle an API response by storing it to state and rendering it.
    """
    response_id = datetime.now().isoformat()
    response_state[response_id] = (request, response)
    if error:
        _render_error(error)
    _render_api_response(request, response, response_id)


def _tool_output_callback(
    tool_output: ToolResult, tool_id: str, tool_state: dict[str, ToolResult]
):
    """Handle a tool output by storing it to state and rendering it."""
    tool_state[tool_id] = tool_output
    _render_message(Sender.TOOL, tool_output)


def _render_api_response(
    request: httpx.Request,
    response: httpx.Response | object | None,
    response_id: str,
):
    """Render an API response to a streamlit tab"""
    print(response)
        #with st.expander(f"Request/Response ({response_id})"):
        #    newline = "\n\n"
        #    st.markdown(
        #        f"`{request.method} {request.url}`{newline}{newline.join(f'`{k}: {v}`' for k, v in request.headers.items())}"
        #    )
        #    st.json(request.read().decode())
        #    st.markdown("---")
        #    if isinstance(response, httpx.Response):
        #        st.markdown(
        #            f"`{response.status_code}`{newline}{newline.join(f'`{k}: {v}`' for k, v in response.headers.items())}"
        #        )
        #        st.json(response.text)
        #    else:
        #        st.write(response)


def _render_error(error: Exception):
    if isinstance(error, RateLimitError):
        body = "You have been rate limited."
        if retry_after := error.response.headers.get("retry-after"):
            body += f" **Retry after {str(timedelta(seconds=int(retry_after)))} (HH:MM:SS).** See our API [documentation](https://docs.anthropic.com/en/api/rate-limits) for more details."
        body += f"\n\n{error.message}"
    else:
        body = str(error)
        body += "\n\n**Traceback:**"
        lines = "\n".join(traceback.format_exception(error))
        body += f"\n\n```{lines}```"
    print(body)

def _render_message(
    sender: Sender,
    message: str | BetaContentBlockParam | ToolResult,
):
    is_tool_result = not isinstance(message, str | dict)
    if not message or (
        is_tool_result
        and not hasattr(message, "error")
        and not hasattr(message, "output")
    ):
        return
    if is_tool_result:
        message = cast(ToolResult, message)
        if message.output:
            if message.__class__.__name__ == "CLIResult":
                print(message.output)
            else:
                print(message.output)
        if message.error:
            print(message.error)
        if message.base64_image:
            print("mdr image")
    elif isinstance(message, dict):
        if message["type"] == "text":
            print(message["text"])
        elif message["type"] == "tool_use":
            print(f'Tool Use: {message["name"]}\nInput: {message["input"]}')
        else:
            # only expected return types are text and tool_use
            raise Exception(f'Unexpected response type {message["type"]}')
    else:
        print(message)


if __name__ == "__main__":
    #a = asyncio.run(ComputerTool().screenshot())

    asyncio.run(main())
