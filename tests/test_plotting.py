import asyncio
import sys
import os
import time
import pytest
import pytest_asyncio
from typing import Type, AsyncIterator

# Import single SessionManager and the interface
from rplayground_mcp.session_manager_interface import (
    ISessionManager,
    ExecutionResult,
    GET_IMAGE_DEST_FUNCTION_NAME
)
from rplayground_mcp.session_manager import SessionManager

# --- Fixtures ---

@pytest_asyncio.fixture
async def manager() -> AsyncIterator[ISessionManager]:
    """Fixture to create and tear down a SessionManager instance."""
    m = SessionManager()
    yield m
    await m.destroy()

# --- Test Function ---

@pytest.mark.asyncio
async def test_plotting(manager: ISessionManager):
    """
    Test basic R plotting functionality with the session manager.
    This tests that the manager correctly returns an image when R generates a plot.
    """
    session_id = await manager.create_session()
    print(f"Created session: {session_id}")
    
    # Basic R code that creates a simple plot
    r_code = f"""
    x <- 1:10
    y <- x^2
    
    # Create a PNG plot - this will be captured by the session manager
    png(filename={GET_IMAGE_DEST_FUNCTION_NAME}(), width=800, height=600)
    plot(x, y, main="Simple Plot", xlab="X axis", ylab="Y axis", col="blue", pch=19)
    dev.off()
    
    # Return a confirmation
    "Plot created successfully"
    """
    
    result = await manager.execute_in_session(session_id, r_code)
    print(f"Execution result: {result['successful_output']}")
    
    # Check there were no errors
    assert not result["r_error_output"], f"R error occurred: {result['r_error_output']}"
    assert not result["system_error_output"], f"System error occurred: {result['system_error_output']}"
    
    # Check we got 1 image back
    assert result["images"], "No images were returned"
    assert len(result["images"]) == 1, f"Expected 1 image, got {len(result['images'])}"
    
    # Check image dimensions match what we requested
    assert result["images"][0].size == (800, 600), f"Image size mismatch: {result['images'][0].size}"
    
    # Clean up the session
    await manager.destroy_session(session_id)