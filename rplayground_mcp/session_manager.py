import logging
import random
import typing
import asyncio
from concurrent.futures import ProcessPoolExecutor
import traceback
import sys
import multiprocessing as mp
logger = logging.getLogger(__name__)

class ExecutionResult(typing.TypedDict):
    successful_output: str | None
    r_error_output: str | None
    system_error_output: str | None


class AsyncRSession:
    def __init__(self):
        # set mode to spawn  
        self.executor = ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context('spawn'))
        self.process_initialized = False
        self.loop = asyncio.get_event_loop()
        
    async def _initialize_process(self):
        if not self.process_initialized:
            # Initialize R in the worker process
            success = await self.loop.run_in_executor(self.executor, _init_r_session)
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
            result = await self.loop.run_in_executor(
                self.executor, _execute_r_code, code
            )
            return result
        except Exception as e:
            # Handle any Python-side errors
            tb = traceback.format_exc()
            return ExecutionResult(
                successful_output=None,
                r_error_output=None,
                system_error_output=f"Python error: {str(e)}\n{tb}"
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


# This global variable is specific to each worker process
r_session = None
rpy2_imported = False

def _init_r_session():
    """Initialize an R session in the worker process."""
    global r_session, rpy2_imported
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
        
        return True
    except Exception as e:
        print(f"Error initializing R session: {str(e)}", file=sys.stderr)
        return False


def _execute_r_code(code: str) -> ExecutionResult:
    """Execute R code in the worker process."""
    global r_session, rpy2_imported
    
    if not rpy2_imported:
        return ExecutionResult(
            successful_output=None,
            r_error_output=None,
            system_error_output="rpy2 not properly imported"
        )
    
    if r_session is None:
        return ExecutionResult(
            successful_output=None,
            r_error_output=None,
            system_error_output="R session not initialized"
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
        output_lines = result_list.rx2('output') # type: ignore
        output_str = "\n".join(str(line) for line in output_lines) if len(output_lines) > 0 else ""
        
        # Get the result value
        r_result = result_list.rx2('result') # type: ignore
        result_str = str(r_result)
        
        # Combine output and result
        if output_str and result_str:
            combined_output = output_str + "\n" + result_str
        else:
            combined_output = output_str or result_str
            
        return ExecutionResult(
            successful_output=combined_output,
            r_error_output=None,
            system_error_output=None
        )
    except RRuntimeError as e:
        # Runtime error from R (like accessing non-existent variable)
        return ExecutionResult(
            successful_output=None,
            r_error_output=str(e),
            system_error_output=None
        )
    except RParsingError as e:
        # R code parsing error (like syntax error)
        return ExecutionResult(
            successful_output=None,
            r_error_output=f"R parsing error: {str(e)}",
            system_error_output=None
        )
    except Exception as e:
        # Other Python error
        tb = traceback.format_exc()
        return ExecutionResult(
            successful_output=None,
            r_error_output=None,
            system_error_output=f"Python error: {str(e)}\n{tb}"
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
                system_error_output=f"Session {session_id} does not exist"
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
        for session_id in self.sessions:
            await self.destroy_session(session_id)
