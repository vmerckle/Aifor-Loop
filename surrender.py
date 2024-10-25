#!/bin/python

import asyncio
import argparse
import platform
import base64
import os
import subprocess
import traceback
import json
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

SYSTEM_PROMPT = f"""
<SYSTEM_CAPABILITY>
* You are are in control of a machine using {platform.machine()} architecture and running {platform.freedesktop_os_release()['NAME']}. Please don't delete anything unless asked three times.
* To launch a program, use nohup. For example to run firefox, use your bash tool with the command nohup firefox. Do not use '&' with the bash tool to run a command in the background.
* When viewing a page it can be helpful to zoom out so that you can see everything on the page.  Either that, or make sure you scroll down to see everything before deciding something isn't available.
* When using your computer function calls, they take a while to run and send back to you.  Where possible/feasible, try to chain multiple of these calls all into one function calls request.
</SYSTEM_CAPABILITY>

<IMPORTANT>
* When using Firefox, click on the address bar where it says "Search or enter address", and enter the appropriate search term or URL there.
* When using Gmail, click in the middle of the research bar area. Do not click on the search icon.
</IMPORTANT>
"""

notused = """
* When using your bash tool with commands that are expected to output very large quantities of text, redirect into a tmp file and use str_replace_editor or `grep -n -B <lines before> -A <lines after> <query> <filename>` to confirm output.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
* When entering text, make sure to delete the text already there if you correct a mistake.
* Take a screenshot BEFORE clicking on a tool so that you can check if the tooltip is coherent with what you want to do.
* Xournal guide: to add a picture, locate the picture tool which looks like a small icon of person on a white background. Confirm you have the right tool by moving the cursor on the tool, and taking a screenshot to see that the text tooltip says 'image'. Then click where you want to add the picture. You then have to click on 'search', then type signature in the top search bar to find 'signature.jpg'. Then you have to click on the signature.jpg file, then open.
"""

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
    only_n_most_recent_images = 1 # important setting to save money.
    hide_images = False

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run the surrender assistant')
    parser.add_argument('prompt', help='The initial prompt for the assistant')
    args = parser.parse_args()
    first_message = args.prompt

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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"conversation_{timestamp}.json"
    
    print(f"Saving {len(messages)} messages to {output_file}")
    with open(output_file, 'w') as f:
        json.dump(messages, f, indent=2, default=str)

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
            pass
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
