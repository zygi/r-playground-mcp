import logging
import random
import typing
import asyncio
from concurrent.futures import ProcessPoolExecutor
import traceback
import sys
import multiprocessing as mp
import tempfile
import os
import glob
from pathlib import Path
from typing import List
from PIL import Image

logger = logging.getLogger(__name__)

class ExecutionResult(typing.TypedDict):
    successful_output: str | None
    r_error_output: str | None
    system_error_output: str | None
    images: List[Image.Image]


class AsyncRSession:
    def __init__(self):
        # set mode to spawn  
        self.executor = ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context('spawn'))
        self.process_initialized = False
        self.loop = asyncio.get_event_loop()
        self.temp_dir = tempfile.mkdtemp(prefix="r_session_")
        
    async def _initialize_process(self):
        if not self.process_initialized:
            # Initialize R in the worker process
            temp_dir = self.temp_dir
            success = await self.loop.run_in_executor(self.executor, _init_r_session, temp_dir)
            if not success:
                raise RuntimeError("Failed to initialize R session")
            self.process_initialized = True
    
    async def execute(self, code: str) -> ExecutionResult:
        # Make sure process is initialized
        if not self.process_initialized:
            logger.info("Starting to initialize process")
            await self._initialize_process()
            logger.info(f"Process initialized: {self.process_initialized}")
        try:
            # Execute R code in the worker process
            temp_dir = self.temp_dir
            result = await self.loop.run_in_executor(
                self.executor, _execute_r_code, code, temp_dir
            )
            return result
        except Exception as e:
            # Handle any Python-side errors
            tb = traceback.format_exc()
            return ExecutionResult(
                successful_output=None,
                r_error_output=None,
                system_error_output=f"Python error: {str(e)}\n{tb}",
                images=[]
            )
    
    async def destroy(self):
        if self.process_initialized:
            try:
                # Shutdown the R session
                await self.loop.run_in_executor(self.executor, _shutdown_r_session)
            except Exception:
                pass  # Ignore errors during shutdown
            finally:
                # Shutdown the executor
                self.executor.shutdown(wait=False)
                self.process_initialized = False
                # Clean up temp directory
                try:
                    for file in glob.glob(os.path.join(self.temp_dir, "*")):
                        os.remove(file)
                    os.rmdir(self.temp_dir)
                except Exception as e:
                    logger.error(f"Error cleaning up temp directory: {e}")


# This global variable is specific to each worker process
r_session = None
rpy2_imported = False
r_temp_dir = None

GET_IMAGE_DEST_FUNCTION_NAME = "get_img_dest_file_name"
IMAGE_WRITING_DESCRIPTION = f"""
You are allowed to output plots and images from your R code. To do so, you should use the function \
{GET_IMAGE_DEST_FUNCTION_NAME}(extension="png") to get a magic filename. If you then write \
the plot to the filename, it will be returned as part of this tool's results.
You can write the images using any R mechanisms, e.g. by creating an R device with `png(filename=get_img_dest_file_name(), width=..., height=...)`.
"""

def _init_r_session(temp_dir: str):
    """Initialize an R session in the worker process."""
    global r_session, rpy2_imported, r_temp_dir
    r_temp_dir = temp_dir
    try:
        import rpy2.robjects as robjects
        from rpy2.robjects import r
        # Import the specific error classes we need to catch
        from rpy2.rinterface_lib.embedded import RRuntimeError
        from rpy2.rinterface_lib._rinterface_capi import RParsingError
        
        # Store imports for later use
        rpy2_imported = True
        
        # Store R session for this process
        r_session = r
        
        # Create a session environment
        r_session("session_env <- new.env()")
        
        # Create a function to generate random filenames within the temp directory
        setup_code = f"""
        .session_plot_dir <- "{temp_dir}"
        {GET_IMAGE_DEST_FUNCTION_NAME} <- function(extension = "png") {{
            file.path(.session_plot_dir, paste0("plot_", format(Sys.time(), "%Y%m%d%H%M%S"), "_", 
                                              floor(runif(1, 1000, 9999)), ".", extension))
        }}
        """
        r_session(setup_code)
        
        return True
    except Exception as e:
        print(f"Error initializing R session: {str(e)}", file=sys.stderr)
        return False


def _execute_r_code(code: str, temp_dir: str) -> ExecutionResult:
    """Execute R code in the worker process."""
    global r_session, rpy2_imported
    
    if not rpy2_imported:
        return ExecutionResult(
            successful_output=None,
            r_error_output=None,
            system_error_output="rpy2 not properly imported",
            images=[]
        )
    
    if r_session is None:
        return ExecutionResult(
            successful_output=None,
            r_error_output=None,
            system_error_output="R session not initialized",
            images=[]
        )
    
    # Import the error types we need to catch
    from rpy2.rinterface_lib.embedded import RRuntimeError
    from rpy2.rinterface_lib._rinterface_capi import RParsingError
    
    try:
        # We need to capture both return values and printed output
        # Use the R capture.output function to capture printed output
        wrapper_code = f"""
        output <- capture.output({{
            result <- local({{{code}}}, envir=session_env)
        }}, type="output")
        
        # Return both the output and result
        list(output=output, result=result)
        """
        
        # Execute the wrapped code
        result_list = r_session(wrapper_code)
        
        # Get captured output
        output_lines = result_list.rx2('output')  # type: ignore
        output_str = "\n".join(str(line) for line in output_lines) if len(output_lines) > 0 else ""
        
        # Get the result value
        r_result = result_list.rx2('result')  # type: ignore
        result_str = str(r_result)
        
        # Combine output and result
        if output_str and result_str:
            combined_output = output_str + "\n" + result_str
        else:
            combined_output = output_str or result_str
        
        # Collect images
        images = []
        for img_path in glob.glob(os.path.join(temp_dir, "plot_*.png")):
            try:
                img = Image.open(img_path)
                images.append(img)
                # Remove the file after loading
                os.remove(img_path)
            except Exception as e:
                logger.error(f"Error loading image {img_path}: {e}")
            
        return ExecutionResult(
            successful_output=combined_output,
            r_error_output=None,
            system_error_output=None,
            images=images
        )
    except RRuntimeError as e:
        # Runtime error from R (like accessing non-existent variable)
        return ExecutionResult(
            successful_output=None,
            r_error_output=str(e),
            system_error_output=None,
            images=[]
        )
    except RParsingError as e:
        # R code parsing error (like syntax error)
        return ExecutionResult(
            successful_output=None,
            r_error_output=f"R parsing error: {str(e)}",
            system_error_output=None,
            images=[]
        )
    except Exception as e:
        # Other Python error
        tb = traceback.format_exc()
        return ExecutionResult(
            successful_output=None,
            r_error_output=None,
            system_error_output=f"Python error: {str(e)}\n{tb}",
            images=[]
        )


def _shutdown_r_session():
    """Shutdown the R session in the worker process."""
    global r_session
    
    if r_session is None:
        return True
    
    try:
        # Clear the environment to free memory
        r_session("rm(list=ls(session_env), envir=session_env)")
        r_session("rm(session_env)")
        r_session("gc()")
        return True
    except Exception:
        return False


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, AsyncRSession] = {}

    async def create_session(self, session_id: str | None = None) -> str:
        if session_id is None:
            session_id = str(random.randint(10000000, 99999999))

        if session_id in self.sessions:
            await self.destroy_session(session_id)
        
        self.sessions[session_id] = AsyncRSession()
        return session_id
        
    async def execute_in_session(self, session_id: str, code: str) -> ExecutionResult:
        if session_id not in self.sessions:
            return ExecutionResult(
                successful_output=None, 
                r_error_output=None,
                system_error_output=f"Session {session_id} does not exist",
                images=[]
            )
        
        logger.info(f"Executing code in session {session_id}: {code}")
        session = self.sessions[session_id]
        result = await session.execute(code)
        logger.info(f"Got result: {result}")
        return result
        
    async def destroy_session(self, session_id: str):
        if session_id in self.sessions:
            await self.sessions[session_id].destroy()
            del self.sessions[session_id]
            return True
        return False
    
    async def destroy(self):
        for session_id in list(self.sessions.keys()):
            await self.destroy_session(session_id)
