#!/usr/bin/env python3

import asyncio
import pytest
import pytest_asyncio
from typing import cast, Type, AsyncIterator

# Import the single SessionManager implementation and the interface
from rplayground_mcp.session_manager_interface import ISessionManager, ExecutionResult
from rplayground_mcp.session_manager import SessionManager

@pytest_asyncio.fixture
async def manager() -> AsyncIterator[ISessionManager]:
    """Fixture to create and tear down a SessionManager instance."""
    m = SessionManager()
    yield m
    await m.destroy()

# Helper function for assertions
def assert_execution_success(result: ExecutionResult, expected_output_substring: str | None = None):
    """Asserts that the execution was successful and optionally checks output content."""
    assert result["successful_output"] is not None, "Expected successful output, but got None."
    assert result["r_error_output"] is None, f"Expected no R error, but got: {result['r_error_output']}"
    assert result["system_error_output"] is None, f"Expected no system error, but got: {result['system_error_output']}"
    if expected_output_substring is not None:
        assert expected_output_substring in cast(str, result["successful_output"])

def assert_execution_r_error(result: ExecutionResult, expected_error_substring: str | None = None):
    """Asserts that the execution resulted in an R error and optionally checks error content."""
    assert result["successful_output"] is None, f"Expected no successful output, but got: {result['successful_output']}"
    assert result["r_error_output"] is not None, "Expected R error output, but got None."
    assert result["system_error_output"] is None, f"Expected no system error, but got: {result['system_error_output']}"
    if expected_error_substring is not None:
        assert expected_error_substring.lower() in cast(str, result["r_error_output"]).lower()

# --- Test Functions ---

@pytest.mark.asyncio
async def test_basic_r_execution(manager: ISessionManager):
    """Test executing a simple R command and getting the result."""
    session_id = await manager.create_session()
    code = "1 + 1"
    result = await manager.execute_in_session(session_id, code)
    assert_execution_success(result, expected_output_substring="2")
    await manager.destroy_session(session_id)

@pytest.mark.asyncio
async def test_r_error_handling(manager: ISessionManager):
    """Test that R errors are properly caught and reported."""
    session_id = await manager.create_session()
    code = "non_existent_variable"
    result = await manager.execute_in_session(session_id, code)
    assert_execution_r_error(result, expected_error_substring="not found")
    await manager.destroy_session(session_id)

@pytest.mark.asyncio
async def test_console_output_capture(manager: ISessionManager):
    """Test that console output is properly captured."""
    session_id = await manager.create_session()
    code = """
    cat("Hello from R!\\n")
    print("This is a test message")
    """
    result = await manager.execute_in_session(session_id, code)
    assert_execution_success(result, expected_output_substring="Hello from R!")
    assert "This is a test message" in cast(str, result["successful_output"])
    await manager.destroy_session(session_id)

@pytest.mark.asyncio
async def test_session_persistence(manager: ISessionManager):
    """Test that variables persist within a session."""
    session_id = await manager.create_session()
    await manager.execute_in_session(session_id, "x <- 42")
    code2 = "x * 2"
    result = await manager.execute_in_session(session_id, code2)
    assert_execution_success(result, expected_output_substring="84")
    await manager.destroy_session(session_id)

@pytest.mark.asyncio
async def test_session_isolation(manager: ISessionManager):
    """Test that multiple sessions are isolated from each other."""
    session_id_1 = await manager.create_session("session_iso_1")
    session_id_2 = await manager.create_session("session_iso_2")
    
    try:
        await manager.execute_in_session(session_id_1, "x <- 100")
        await manager.execute_in_session(session_id_2, "x <- 200")
        result1 = await manager.execute_in_session(session_id_1, "x")
        result2 = await manager.execute_in_session(session_id_2, "x")
        assert_execution_success(result1, expected_output_substring="100")
        assert_execution_success(result2, expected_output_substring="200")
    finally:
        await asyncio.gather(
            manager.destroy_session(session_id_1),
            manager.destroy_session(session_id_2)
        )

@pytest.mark.asyncio
async def test_complex_data_structures(manager: ISessionManager):
    """Test handling of more complex R data structures."""
    session_id = await manager.create_session()
    code = """
    df <- data.frame(
        name = c("Alice", "Bob", "Charlie"),
        age = c(25, 30, 35),
        score = c(90, 85, 95)
    )
    mean_age <- mean(df$age)
    max_score <- max(df$score)
    list(
        data = df,
        stats = list(mean_age = mean_age, max_score = max_score)
    )
    """
    result = await manager.execute_in_session(session_id, code)
    assert_execution_success(result)
    output = cast(str, result["successful_output"])
    assert "name" in output
    assert "Alice" in output
    assert "age" in output
    assert "score" in output
    assert "mean_age" in output
    assert "30" in output
    assert "max_score" in output
    assert "95" in output
    await manager.destroy_session(session_id)

@pytest.mark.asyncio
async def test_concurrent_interleaved_execution(manager: ISessionManager):
    """Test multiple sessions with interleaved commands executing concurrently."""
    session_ids = [f"conc_sess_{i}" for i in range(1, 4)]
    await asyncio.gather(*(manager.create_session(sid) for sid in session_ids))
    
    try:
        async def session_task(session_id: str, base_value: int) -> ExecutionResult:
            """Run a sequence of commands and return the final result."""
            await manager.execute_in_session(session_id, f"counter <- {base_value}")
            await manager.execute_in_session(
                session_id, 
                f'''
                df <- data.frame(
                    id = c(1, 2, 3),
                    value = c({base_value}, {base_value+1}, {base_value+2})
                )
                '''
            )
            await manager.execute_in_session(session_id, "counter <- counter + sum(df$value)")
            return await manager.execute_in_session(session_id, "counter")
        
        tasks = [
            session_task(session_ids[0], 100),
            session_task(session_ids[1], 200),
            session_task(session_ids[2], 300)
        ]
        final_results = await asyncio.gather(*tasks)
        
        expected_values = ["403", "803", "1203"]
        for i, final_result in enumerate(final_results):
            assert_execution_success(final_result, expected_output_substring=expected_values[i])
    
    finally:
        await asyncio.gather(*(manager.destroy_session(sid) for sid in session_ids))