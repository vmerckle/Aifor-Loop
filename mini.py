import asyncio
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

CONFIG_DIR = PosixPath("~/.anthropic").expanduser()
API_KEY_FILE = CONFIG_DIR / "api_key"
STREAMLIT_STYLE = """
<style>
    /* Hide chat input while agent loop is running */
    .stApp[data-teststate=running] .stChatInput textarea,
    .stApp[data-test-script-state=running] .stChatInput textarea {
        display: none;
    }
     /* Hide the streamlit deploy button */
    .stAppDeployButton {
        visibility: hidden;
    }
</style>
"""

WARNING_TEXT = "⚠️ Security Alert: Never provide access to sensitive accounts or data, as malicious web content can hijack Claude's behavior"


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

    new_message = "Let's create a file named test with a nice poem inside, in /tmp. That's it."
    new_message = "Just take a screenshot and tell me what's in it."
    new_message = "Close the firefox tab. Use only the mouse!"
    new_message = "Open firefox and watch some yellow stone"
    new_message = "Just take a screenshot and tell me what's in it."

    messages = []
    messages.append(
        {
            "role": Sender.USER,
            "content": [BetaTextBlockParam(type="text", text=new_message)],
        }
    )

    messages = await sampling_loop(
        system_prompt_suffix=custom_system_prompt,
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
    """Convert input from the user or output from the agent to a streamlit message."""
    # streamlit's hotreloading breaks isinstance checks, so we need to check for class names
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
    #if is_tool_result:
    #    message = cast(ToolResult, message)
    #    if message.output:
    #        if message.__class__.__name__ == "CLIResult":
    #            st.code(message.output)
    #        else:
    #            st.markdown(message.output)
    #    if message.error:
    #        st.error(message.error)
    #    if message.base64_image and not st.session_state.hide_images:
    #        st.image(base64.b64decode(message.base64_image))
    #elif isinstance(message, dict):
    #    if message["type"] == "text":
    #        st.write(message["text"])
    #    elif message["type"] == "tool_use":
    #        st.code(f'Tool Use: {message["name"]}\nInput: {message["input"]}')
    #    else:
    #        # only expected return types are text and tool_use
    #        raise Exception(f'Unexpected response type {message["type"]}')
    #else:
    #    st.markdown(message)


if __name__ == "__main__":
    tl = "{'id': 'toolu_011zRDBiwpyemE9dUA4RCSne', 'input': {'action': 'screenshot'}, 'name': 'computer', 'type': 'tool_use'}"
    #a = asyncio.run(ComputerTool().screenshot())


    asyncio.run(main())
