import asyncio
import base64
from contextlib import asynccontextmanager
import importlib.util
import io
import json
import logging
import PIL.Image
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import ImageContent, TextContent, EmbeddedResource, BlobResourceContents
from mcp.server.fastmcp.prompts.base import Message
import typing
import httpx
from pydantic import AnyUrl
import tempfile
from pathlib import Path


from rplayground_mcp.configuration import Configuration
from rplayground_mcp.prompts import PROMPT_REVIEW_PAPER
from rplayground_mcp.session_manager import SessionManager
from rplayground_mcp import utils
from rplayground_mcp.session_manager_interface import IMAGE_WRITING_DESCRIPTION
from rplayground_mcp.pdf_conversion.converter_subprocess import MarkerConverter

logger = logging.getLogger(__name__)

PDF_CONVERTER: MarkerConverter | None = None
if importlib.util.find_spec("marker") is not None:
    from rplayground_mcp.pdf_conversion.converter_subprocess_impl import MPMarkerConverter
    PDF_CONVERTER = MPMarkerConverter()
else:
    PDF_CONVERTER = None
    logger.warning("Marker not installed, PDF conversion will not be available")


class AppContext(typing.TypedDict):
    session_manager: SessionManager

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> typing.AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    # Initialize on startup
    session_manager = SessionManager()

    # if PDF_CONVERTER is not None:
    #     asyncio.create_task(setup_pdf_converter())

    if PDF_CONVERTER is not None:
        PDF_CONVERTER.start()
    try:
        yield AppContext(session_manager=session_manager)
    finally:
        # Cleanup on shutdown
        await session_manager.destroy()

config = Configuration()
mcp = FastMCP("R Playground", lifespan=app_lifespan)

class RExecutionResult(typing.TypedDict):
    session_id: str
    successful_output: str | None
    r_error_output: str | None
    system_error_output: str | None


def mk_mcp_r_tool_description() -> str:
    packages_available = ", ".join([f"{p}" for p in utils.get_r_available_packages()])
    
    if config.support_image_output:
        image_description = "\n" + IMAGE_WRITING_DESCRIPTION + "\n"
    else:
        image_description = "\nYou will not be able to see visual image/plot output. Please try to use code and textual output to achieve your goals."
    return f"""\
Execute an R command in a transient R session. Arguments:
    - command: The R command (or a series of commands) to execute in the REPL session.
    - r_session_id: The ID of the session to execute the command in. If not provided, a new session will be created. Leave blank the first time you call this tool.
To avoid losing too much work, prefer to call this tool in small chunks of commands. Don't just output the entire massive script at once.
More concretely: no more than 100 LOC at a time.

{image_description}
The packages you have available in the R session are:
{packages_available}

You are allowed to install new packages if you need to.
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
    
    if len(image_contents) > 0:
        return (result_text,) + tuple(image_contents)
    else:
        return result_text


@mcp.prompt("review_paper_prompt", description="Review a paper for statistical errors and other issues.")
async def review_paper() -> list[Message]:
    text = Message(
        role="user",
        content=TextContent(type="text", text=PROMPT_REVIEW_PAPER)
    )  
    return [text]



# async def setup_pdf_converter():

if PDF_CONVERTER is not None:
    assert PDF_CONVERTER is not None
    # await PDF_CONVERTER.wait_for_startup()
    logger.info("PDF converter initialized")

    @mcp.tool("ocr_paper", description="OCR a PDF from a URL")
    async def ocr_paper(url: str):
        anyurl = AnyUrl(url)
        if anyurl.scheme not in ["http", "https"]:
            raise ValueError("Invalid URL")
        
        # download to temp file
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name
        
                assert PDF_CONVERTER is not None
                logger.info("Waiting for PDF converter startup")
                await PDF_CONVERTER.wait_for_startup()
                rendered = await PDF_CONVERTER.convert(Path(temp_file_path))
                # text, _, images = text_from_rendered(rendered)
                text = rendered["text"]
                image_values = rendered["images"]
        
                return [TextContent(type="text", text=text)] + [
                    ImageContent(type="image", data=img, mimeType="image/png")
                    for (_, img) in list(image_values.items())#[:1]
                ]
                # return (
                #     Message(
                #         role="user",
                #         content=TextContent(type="text", text=text),
                #     )
                # ,) + tuple(
                #     Message(
                #         role="user",
                #         content=EmbeddedResource(type="resource", resource=BlobResourceContents(uri=AnyUrl("embimg://asdf"), blob=img, mimeType="image/png",)),
                #         # content=EmbeddedResource(type="image", data=img, mimeType="image/png",),
                #     )
                #     for (_, img) in list(image_values.items())#[:1]
                # )

def main() -> None:
    mcp.run()

if __name__ == "__main__":
    main()