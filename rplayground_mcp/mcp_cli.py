import base64
from contextlib import asynccontextmanager
import io
import json
import logging
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import ImageContent, TextContent
import typing

from rplayground_mcp.session_manager import IMAGE_WRITING_DESCRIPTION, SessionManager
from rplayground_mcp import utils

logger = logging.getLogger(__name__)

class AppContext(typing.TypedDict):
    session_manager: SessionManager


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> typing.AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    # Initialize on startup
    session_manager = SessionManager()
    try:
        yield AppContext(session_manager=session_manager)
    finally:
        # Cleanup on shutdown
        await session_manager.destroy()

mcp = FastMCP("R Playground", lifespan=app_lifespan)

class RExecutionResult(typing.TypedDict):
    session_id: str
    successful_output: str | None
    r_error_output: str | None
    system_error_output: str | None


def mk_mcp_r_tool_description() -> str:
    packages_available = ", ".join([f"{p}" for p in utils.get_r_available_packages()])
    return f"""\
Execute an R command in a transient R session. Arguments:
    - command: The R command (or a series of commands) to execute in the REPL session.
    - r_session_id: The ID of the session to execute the command in. If not provided, a new session will be created. Leave blank the first time you call this tool.

{IMAGE_WRITING_DESCRIPTION}

The packages you have available in the R session are:
{packages_available}
"""

@mcp.tool(description=mk_mcp_r_tool_description())
async def execute_r_command(ctx: Context, command: str, r_session_id: str | None = None):
    logger.info("Request received for session %s", r_session_id)
    manager = ctx.request_context.lifespan_context["session_manager"]
    assert isinstance(manager, SessionManager)
    if r_session_id is None:
        logger.info("Creating new R session")
        try:
            r_session_id = await manager.create_session()
        except Exception as e:
            return RExecutionResult(
                session_id="",
                successful_output=None,
                r_error_output=None,
                system_error_output=str(e),
            )

    result = await manager.execute_in_session(r_session_id, command)
    main_res = RExecutionResult(
        session_id=r_session_id,
        successful_output=result["successful_output"],
        r_error_output=result["r_error_output"],
        system_error_output=result["system_error_output"],
    )

    result_text = TextContent(type="text", text=json.dumps(main_res))
    image_contents = []
    for img in result["images"]:
        with io.BytesIO() as buffer:
            img.save(buffer, format="PNG")
            img_bytes = buffer.getvalue()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            image_contents.append(ImageContent(type="image", data=img_base64, mimeType="image/png"))
    
    return (result_text,) + tuple(image_contents)


if __name__ == "__main__":
    mcp.run()
