import typing
from abc import ABC, abstractmethod
from typing import List
from PIL import Image

# Define the common result structure
class ExecutionResult(typing.TypedDict):
    successful_output: str | None
    r_error_output: str | None
    system_error_output: str | None
    images: List[Image.Image]

# Define the interface using an Abstract Base Class
class ISessionManager(ABC):
    @abstractmethod
    async def create_session(self, session_id: str | None = None) -> str:
        """Creates a new execution session.

        Args:
            session_id: An optional specific ID for the session.

        Returns:
            The ID of the created session.
        """
        pass

    @abstractmethod
    async def execute_in_session(self, session_id: str, code: str) -> ExecutionResult:
        """Executes R code within a specific session.

        Args:
            session_id: The ID of the session to use.
            code: The R code string to execute.

        Returns:
            An ExecutionResult dictionary containing output, errors, and images.
        """
        pass

    @abstractmethod
    async def destroy_session(self, session_id: str) -> bool:
        """Destroys a specific session and cleans up resources.

        Args:
            session_id: The ID of the session to destroy.

        Returns:
            True if the session existed and was destroyed, False otherwise.
        """
        pass

    @abstractmethod
    async def destroy(self) -> None:
        """Destroys all active sessions managed by this manager."""
        pass

# Common constants can also live here if desired
GET_IMAGE_DEST_FUNCTION_NAME = "get_img_dest_file_name"
IMAGE_WRITING_DESCRIPTION = f"""
You are allowed to output plots and images from your R code. To do so, you should use the function \
{GET_IMAGE_DEST_FUNCTION_NAME}(extension="png") to get a magic filename. If you then write \
the plot to the filename, it will be returned as part of this tool's results.
You can write the images using any R mechanisms, e.g. by creating an R device with `png(filename=get_img_dest_file_name(), width=..., height=...)`.
""" 