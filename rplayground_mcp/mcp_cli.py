from contextlib import asynccontextmanager
import logging
import httpx
from mcp.server.fastmcp import FastMCP, Context
import typing

from session_manager import SessionManager

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

@mcp.tool()
async def execute_r_command(ctx: Context, command: str, r_session_id: str | None = None) -> RExecutionResult:
    """Execute an R command in a transient session. Arguments:
    - command: The R command (or a series of commands) to execute in the REPL session.
    - r_session_id: The ID of the session to execute the command in. If not provided, a new session will be created. Leave blank the first time you call this tool.
    """
    logger.info("Request received")
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
    
    logger.info(f"Executing command in session {r_session_id}: {command}")
    
    result = await manager.execute_in_session(r_session_id, command)
    
    logger.info(f"Got result: {result}")
    return RExecutionResult(
        session_id=r_session_id,
        successful_output=result["successful_output"],
        r_error_output=result["r_error_output"],
        system_error_output=result["system_error_output"],
    )