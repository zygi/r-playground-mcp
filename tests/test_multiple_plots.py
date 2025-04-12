import pytest
import pytest_asyncio
from typing import AsyncIterator

from rplayground_mcp.session_manager_interface import (
    ISessionManager,
    GET_IMAGE_DEST_FUNCTION_NAME,
)
from rplayground_mcp.session_manager import SessionManager


@pytest_asyncio.fixture
async def manager() -> AsyncIterator[ISessionManager]:
    """Fixture to create and tear down a SessionManager instance."""
    m = SessionManager()
    yield m
    await m.destroy()


@pytest.mark.asyncio
async def test_multiple_plots(manager: ISessionManager):
    """
    Test creating multiple plots sequentially in a single R session,
    checking each one is returned correctly.
    """
    session_id = await manager.create_session()
    print(f"Created session: {session_id}")

    setup_code = """
    set.seed(123)
    x <- 1:50
    y1 <- 2*x + rnorm(50, mean=0, sd=10)
    y2 <- 3*x + rnorm(50, mean=5, sd=15)
    df <- data.frame(x=x, y1=y1, y2=y2)
    
    "Dataset created"
    """

    result = await manager.execute_in_session(session_id, setup_code)
    print(f"Setup result: {result['successful_output']}")
    assert not result["r_error_output"], f"Setup failed: {result['r_error_output']}"
    assert not result["system_error_output"]
    assert not result["images"]  # No images expected from setup

    # Helper function to execute and check a plot
    async def check_plot(plot_code: str, plot_name: str):
        print(f"--- Creating {plot_name} ---")
        exec_result = await manager.execute_in_session(session_id, plot_code)
        print(f"{plot_name} R output: {exec_result['successful_output']}")

        if exec_result["r_error_output"]:
            pytest.fail(f"R error during {plot_name}: {exec_result['r_error_output']}")
        if exec_result["system_error_output"]:
            pytest.fail(
                f"System error during {plot_name}: {exec_result['system_error_output']}"
            )

        print(f"{plot_name} images captured: {len(exec_result['images'])}")
        assert exec_result["images"], f"No image captured for {plot_name}"
        assert (
            len(exec_result["images"]) == 1
        ), f"Expected 1 image for {plot_name}, got {len(exec_result['images'])}"
        assert exec_result["images"][0].size == (
            800,
            600,
        ), f"{plot_name} size mismatch: {exec_result['images'][0].size}"
        print(f"--- {plot_name} check passed ---")

    scatter_code = f"""
    png(filename={GET_IMAGE_DEST_FUNCTION_NAME}(), width=800, height=600)
    plot(df$x, df$y1, main=\"Scatter Plot\", 
         xlab=\"X Values\", ylab=\"Y Values\",
         col=\"blue\", pch=19)
    dev.off()
    
    "Scatter plot created"
    """
    await check_plot(scatter_code, "Scatter Plot")

    bar_code = f"""
    png(filename={GET_IMAGE_DEST_FUNCTION_NAME}(), width=800, height=600)
    barplot(df$y2[1:10], names.arg=df$x[1:10], 
            main=\"Bar Plot\", xlab=\"X Values\", ylab=\"Y2 Values\",
            col=\"green\")
    dev.off()
    
    "Bar plot created"
    """
    await check_plot(bar_code, "Bar Plot")

    hist_code = f"""
    png(filename={GET_IMAGE_DEST_FUNCTION_NAME}(), width=800, height=600)
    hist(df$y1, main=\"Histogram\", xlab=\"Y1 Values\",
         col=\"purple\", breaks=15)
    dev.off()
    
    "Histogram created"
    """
    await check_plot(hist_code, "Histogram")

    # Clean up the specific session
    await manager.destroy_session(session_id)
