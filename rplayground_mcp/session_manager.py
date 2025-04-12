import logging
import random
import traceback
import tempfile
import os
import glob
from PIL import Image
import rpy2.robjects as robjects
from rpy2.robjects import r

# Import the specific error classes we need to catch
from rpy2.rinterface_lib.embedded import RRuntimeError
from rpy2.rinterface_lib._rinterface_capi import RParsingError

# Import from the interface
from .session_manager_interface import (
    ISessionManager,
    ExecutionResult,
    GET_IMAGE_DEST_FUNCTION_NAME,
)

logger = logging.getLogger(__name__)

# --- R Environment Setup ---
try:
    logger.info(
        f"Initializing R global instance using R_HOME: {os.environ.get('R_HOME', 'Not Set')}"
    )
    # Initialize R embedded instance - This happens once per process
    r_instance = r
    logger.info("R instance initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize R instance: {e}", exc_info=True)
    # Depending on the application, you might want to raise an error or exit
    r_instance = None  # Indicate failure


class AsyncRSession:
    def __init__(self, session_id: str, r_instance):
        self.session_id = session_id
        self.r = r_instance
        self.env_name = f"session_env_{self.session_id}"
        self.temp_dir = tempfile.mkdtemp(prefix=f"r_session_{self.session_id}_")
        self.session_env = None

        if self.r is None:
            raise RuntimeError("R instance is not available.")

        try:
            # Create a new environment for this session
            logger.debug(f"Creating R environment: {self.env_name}")
            self.r(f"{self.env_name} <- new.env(parent = globalenv())")
            self.session_env = self.r[
                self.env_name
            ]  # Get a reference to the environment

            # Define the image helper function within the session's environment
            # Note: Using R's `assign` to put it directly into the environment
            setup_code = f"""
            local({{
                # Set the locale to C to force ASCII and English messages
                Sys.setenv(LC_ALL='C')

                # Set a default CRAN mirror to avoid interactive prompts for install.packages
                options(repos = c(CRAN = "https://cran.rstudio.com/"))

                .session_plot_dir <- "{self.temp_dir.replace(os.sep, '/')}" # Ensure forward slashes for R path compatibility
                img_func <- function(extension = "png") {{
                    file.path(.session_plot_dir, paste0("plot_", format(Sys.time(), "%Y%m%d%H%M%S"), "_",
                                                      floor(runif(1, 1000, 9999)), ".", extension))
                }}
                assign("{GET_IMAGE_DEST_FUNCTION_NAME}", img_func, envir = parent.env(environment()))
            }}, envir = {self.env_name})
            """
            logger.debug(
                f"Defining helper functions and setting options in {self.env_name}"
            )
            self.r(setup_code)
            logger.info(
                f"Initialized R session {self.session_id} with env {self.env_name} and temp dir {self.temp_dir}"
            )

        except Exception as e:
            logger.error(
                f"Error initializing session environment {self.env_name}: {e}",
                exc_info=True,
            )
            # Cleanup if initialization failed partially
            self._cleanup_temp_dir()
            raise RuntimeError(
                f"Failed to initialize R session environment {self.env_name}: {e}"
            )

    async def execute(self, code: str) -> ExecutionResult:
        if self.r is None or self.session_env is None:
            return ExecutionResult(
                successful_output=None,
                r_error_output=None,
                system_error_output="R session not properly initialized",
                images=[],
            )

        try:
            # Wrap code to capture output and execute in the session environment
            # Use triple quotes and escape sequences correctly for the R code string
            wrapper_code = f"""
            output <- capture.output({{
                # Using `tryCatch` within R to potentially capture R errors more granularly if needed
                # For now, relying on rpy2's exception handling for RRuntimeError/RParsingError
                result <- local({{{code}}}, envir={self.env_name})
            }}, type="output")

            # Return both the output and result
            list(output=output, result=result)
            """

            logger.debug(f"Executing code in {self.env_name}: {code[:100]}...")
            # Execute the code within the specific session environment
            result_list = self.r(
                wrapper_code
            )  # Evaluation happens in global, but `local` call targets the session_env

            # Get captured output
            output_lines = result_list.rx2("output")  # type: ignore
            output_str = (
                "\n".join(str(line) for line in output_lines)
                if len(output_lines) > 0
                else ""
            )

            # Get the result value
            r_result = result_list.rx2("result")  # type: ignore
            # Handle potential NULL results more gracefully
            result_str = str(r_result) if r_result is not robjects.NULL else ""

            # Combine output and result logic (corrected formatting)
            if (
                output_str and result_str and not result_str.startswith("[1]")
            ):  # Avoid redundant print of simple results
                combined_output = output_str + "\n" + result_str
            elif output_str and result_str:
                # R often prints the result itself to output if not assigned and it's the last expression
                # Check if result string is essentially contained within the output string
                if result_str.strip() in output_str.strip():
                    combined_output = output_str
                else:
                    combined_output = output_str + "\n" + result_str
            else:
                combined_output = output_str or result_str

            # Collect images
            images = []
            # Ensure forward slashes for glob compatibility if needed, though os.path.join should handle it
            search_path = os.path.join(self.temp_dir, "plot_*.png")
            logger.debug(f"Searching for images in: {search_path}")
            for img_path in glob.glob(search_path):
                try:
                    logger.debug(f"Loading image: {img_path}")
                    # Ensure image file is closed after loading
                    with Image.open(img_path) as img:
                        # Make a copy to work with after the file is closed
                        images.append(img.copy())
                    # Remove the file after loading
                    os.remove(img_path)
                    logger.debug(f"Removed image file: {img_path}")
                except Exception as e:
                    logger.error(f"Error processing image {img_path}: {e}")

            logger.debug(
                f"Execution successful in {self.env_name}. Output length: {len(combined_output)}, Images found: {len(images)}"
            )
            return ExecutionResult(
                successful_output=combined_output,
                r_error_output=None,
                system_error_output=None,
                images=images,
            )
        except RRuntimeError as e:
            logger.warning(f"R runtime error in {self.env_name}: {e}")
            return ExecutionResult(
                successful_output=None,
                r_error_output=str(e),
                system_error_output=None,
                images=[],
            )
        except RParsingError as e:
            logger.warning(f"R parsing error in {self.env_name}: {e}")
            return ExecutionResult(
                successful_output=None,
                r_error_output=f"R parsing error: {str(e)}",
                system_error_output=None,
                images=[],
            )
        except Exception as e:
            logger.error(
                f"Python error during execution in {self.env_name}: {e}", exc_info=True
            )
            tb = traceback.format_exc()
            return ExecutionResult(
                successful_output=None,
                r_error_output=None,
                system_error_output=f"Python error: {str(e)}\n{tb}",
                images=[],
            )

    def _cleanup_temp_dir(self):
        """Safely remove the temporary directory and its contents."""
        try:
            if os.path.exists(self.temp_dir):
                logger.debug(f"Cleaning up temp directory: {self.temp_dir}")
                for file in glob.glob(os.path.join(self.temp_dir, "*")):
                    try:
                        os.remove(file)
                    except Exception as e:
                        logger.error(f"Error removing file {file}: {e}")
                os.rmdir(self.temp_dir)
                logger.debug(f"Removed temp directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temp directory {self.temp_dir}: {e}")

    async def destroy(self):
        if self.r is None:
            logger.warning(
                f"Cannot destroy session {self.session_id}, R instance not available."
            )
            return

        try:
            # Remove the specific session environment
            if hasattr(self, "env_name") and self.env_name:
                logger.debug(f"Removing R environment: {self.env_name}")
                # Check if environment exists before trying to remove
                env_exists = self.r(f'exists("{self.env_name}")')[0]
                if env_exists:
                    self.r(f"rm({self.env_name}, envir = globalenv())")
                    logger.info(f"Removed R environment: {self.env_name}")
                else:
                    logger.warning(
                        f"R environment {self.env_name} not found for removal."
                    )
            # Run garbage collection in R
            self.r("gc()")
        except Exception as e:
            logger.error(
                f"Error removing R environment {self.env_name}: {e}", exc_info=True
            )
        finally:
            # Clean up the temp directory regardless of R cleanup success
            self._cleanup_temp_dir()


# Inherit from the interface
class SessionManager(ISessionManager):
    def __init__(self):
        if r_instance is None:
            raise RuntimeError(
                "R global instance failed to initialize. SessionManager cannot operate."
            )
        self.r = r_instance
        self.sessions: dict[str, AsyncRSession] = {}

    async def create_session(self, session_id: str | None = None) -> str:
        if session_id is None:
            # Create a random session ID (ensure it's R-compatible if used directly)
            session_id = f"s{random.randint(10000000, 99999999)}"

        if session_id in self.sessions:
            logger.warning(
                f"Session {session_id} already exists. Destroying previous instance."
            )
            await self.destroy_session(session_id)

        logger.info(f"Creating new session: {session_id}")
        try:
            # RSession creation involves R calls, run in executor if it blocks significantly
            # For now, assume R environment creation is fast enough to do directly
            session = AsyncRSession(session_id, self.r)
            self.sessions[session_id] = session
            logger.info(f"Session {session_id} created successfully.")
            return session_id
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}", exc_info=True)
            # Rethrow or handle as appropriate for the application
            raise

    async def execute_in_session(self, session_id: str, code: str) -> ExecutionResult:
        if session_id not in self.sessions:
            logger.warning(
                f"Attempted to execute in non-existent session: {session_id}"
            )
            return ExecutionResult(
                successful_output=None,
                r_error_output=None,
                system_error_output=f"Session {session_id} does not exist",
                images=[],
            )

        logger.info(f"Executing code in session {session_id}: {code[:100]}...")
        session = self.sessions[session_id]
        # The execute method itself is async, so just await it
        result = await session.execute(code)
        logger.info(f"Execution finished in session {session_id}.")
        return result

    async def destroy_session(self, session_id: str) -> bool:  # Added return type bool
        if session_id in self.sessions:
            logger.info(f"Destroying session: {session_id}")
            session = self.sessions[session_id]
            try:
                await session.destroy()
            except Exception as e:
                logger.error(
                    f"Error during session destroy {session_id}: {e}", exc_info=True
                )
            finally:
                # Ensure session is removed from the manager's list
                if session_id in self.sessions:
                    del self.sessions[session_id]
                logger.info(f"Session {session_id} removed from manager.")
            return True
        else:
            logger.warning(f"Attempted to destroy non-existent session: {session_id}")
            return False

    async def destroy(self):
        """Destroy all managed sessions."""
        logger.info("Destroying all active sessions...")
        # Create a list of session IDs to avoid issues with modifying dict during iteration
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self.destroy_session(session_id)
        logger.info("All sessions destroyed.")
