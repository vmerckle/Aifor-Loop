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

SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are utilising an Ubuntu virtual machine using {platform.machine()} architecture with internet access.
* You can feel free to install Ubuntu applications with your bash tool. Use curl instead of wget.
* To open firefox, please just click on the firefox icon.  Note, firefox is what is installed on your system.
* Using bash tool you can start GUI applications, but you need to set export DISPLAY=:1 and use a subshell. For example "(DISPLAY=:1 xterm &)". GUI apps run with bash tool will appear within your desktop environment, but they may take some time to appear. Take a screenshot to confirm it did.
* When using your bash tool with commands that are expected to output very large quantities of text, redirect into a tmp file and use str_replace_editor or `grep -n -B <lines before> -A <lines after> <query> <filename>` to confirm output.
* When viewing a page it can be helpful to zoom out so that you can see everything on the page.  Either that, or make sure you scroll down to see everything before deciding something isn't available.
* When using your computer function calls, they take a while to run and send back to you.  Where possible/feasible, try to chain multiple of these calls all into one function calls request.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
</SYSTEM_CAPABILITY>

<IMPORTANT>
* When using Firefox, if a startup wizard appears, IGNORE IT.  Do not even click "skip this step".  Instead, click on the address bar where it says "Search or enter address", and enter the appropriate search term or URL there.
* If the item you are looking at is a pdf, if after taking a single screenshot of the pdf it seems that you want to read the entire document instead of trying to continue to read the pdf from your screenshots + navigation, determine the URL, use curl to download the pdf, install and use pdftotext to convert it to a text file, and then read that text file directly with your StrReplaceEditTool.
</IMPORTANT>"""

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
    custom_system_prompt = ""
    hide_images = False

    first_message = "Let's create a file named test with a nice poem inside, in /tmp. That's it."
    first_message = "Just take a screenshot and tell me what's in it."
    first_message = "Close the firefox tab. Use only the mouse!"
    first_message = "Open firefox and watch some yellow stone"
    first_message = "Just take a screenshot and tell me what's in it."


    messages = []
    messages.append(
        {
            "role": Sender.USER,
            "content": [BetaTextBlockParam(type="text", text=first_message)],
        }
    )

    messages = await sampling_loop(
        system_prompt=SYSTEM_PROMPT,
        model=model,
        provider=provider,
        messages=messages,
        output_callback=partial(_render_message, Sender.BOT),
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

    print(f"printing {len(messages)} messages...\n")
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
    print(error)
    #if isinstance(error, RateLimitError):
    #    body = "You have been rate limited."
    #    if retry_after := error.response.headers.get("retry-after"):
    #        body += f" **Retry after {str(timedelta(seconds=int(retry_after)))} (HH:MM:SS).** See our API [documentation](https://docs.anthropic.com/en/api/rate-limits) for more details."
    #    body += f"\n\n{error.message}"
    #else:
    #    body = str(error)
    #    body += "\n\n**Traceback:**"
    #    lines = "\n".join(traceback.format_exception(error))
    #    body += f"\n\n```{lines}```"
    #save_to_storage(f"error_{datetime.now().timestamp()}.md", body)
    #st.error(f"**{error.__class__.__name__}**\n\n{body}", icon=":material/error:")


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
