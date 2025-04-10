#!/usr/bin/env python3

import asyncio
import unittest
from typing import cast

from rplayground_mcp.session_manager import SessionManager, ExecutionResult


class TestSessionManager(unittest.IsolatedAsyncioTestCase):
    """Test the SessionManager and AsyncRSession classes."""
    
    async def asyncSetUp(self):
        """Set up a session manager and create a test session before each test."""
        self.session_manager = SessionManager()
        self.test_session_id = "test_session"
        await self.session_manager.create_session(self.test_session_id)
    
    async def asyncTearDown(self):
        """Clean up sessions after each test."""
        # Ensure the main test session is destroyed even if others are created
        await self.session_manager.destroy_session(self.test_session_id)
    
    def assertExecutionSuccess(self, result: ExecutionResult, expected_output_substring: str | None = None):
        """Asserts that the execution was successful and optionally checks output content."""
        self.assertIsNotNone(result["successful_output"], "Expected successful output, but got None.")
        self.assertIsNone(result["r_error_output"], f"Expected no R error, but got: {result['r_error_output']}")
        self.assertIsNone(result["system_error_output"], f"Expected no system error, but got: {result['system_error_output']}")
        if expected_output_substring is not None:
            # The cast is safe because we asserted successful_output is not None
            self.assertIn(expected_output_substring, cast(str, result["successful_output"]))
    
    def assertExecutionRError(self, result: ExecutionResult, expected_error_substring: str | None = None):
        """Asserts that the execution resulted in an R error and optionally checks error content."""
        self.assertIsNone(result["successful_output"], f"Expected no successful output, but got: {result['successful_output']}")
        self.assertIsNotNone(result["r_error_output"], "Expected R error output, but got None.")
        self.assertIsNone(result["system_error_output"], f"Expected no system error, but got: {result['system_error_output']}")
        if expected_error_substring is not None:
            # The cast is safe because we asserted r_error_output is not None
            self.assertIn(expected_error_substring.lower(), cast(str, result["r_error_output"]).lower())
    
    async def test_basic_r_execution(self):
        """Test executing a simple R command and getting the result."""
        code = "1 + 1"
        result = await self.session_manager.execute_in_session(self.test_session_id, code)
        self.assertExecutionSuccess(result, expected_output_substring="2")
    
    async def test_r_error_handling(self):
        """Test that R errors are properly caught and reported."""
        code = "non_existent_variable"
        result = await self.session_manager.execute_in_session(self.test_session_id, code)
        self.assertExecutionRError(result, expected_error_substring="not found")
    
    async def test_console_output_capture(self):
        """Test that console output is properly captured."""
        code = """
        cat("Hello from R!\n")
        print("This is a test message")
        """
        result = await self.session_manager.execute_in_session(self.test_session_id, code)
        self.assertExecutionSuccess(result, expected_output_substring="Hello from R!")
        # Check for the second message specifically
        self.assertIn("This is a test message", cast(str, result["successful_output"]))
    
    async def test_session_persistence(self):
        """Test that variables persist within a session."""
        # Set a variable
        await self.session_manager.execute_in_session(self.test_session_id, "x <- 42")
        
        # Use the variable in a subsequent command
        code2 = "x * 2"
        result = await self.session_manager.execute_in_session(self.test_session_id, code2)
        self.assertExecutionSuccess(result, expected_output_substring="84")
    
    async def test_session_isolation(self):
        """Test that multiple sessions are isolated from each other."""
        # Create a second session
        second_session_id = "second_test_session"
        await self.session_manager.create_session(second_session_id)
        
        try:
            # Set different variables in each session
            await self.session_manager.execute_in_session(self.test_session_id, "x <- 100")
            await self.session_manager.execute_in_session(second_session_id, "x <- 200")
            
            # Verify the variables have different values in different sessions
            result1 = await self.session_manager.execute_in_session(self.test_session_id, "x")
            result2 = await self.session_manager.execute_in_session(second_session_id, "x")
            
            self.assertExecutionSuccess(result1, expected_output_substring="100")
            self.assertExecutionSuccess(result2, expected_output_substring="200")
        finally:
            # Clean up the second session
            await self.session_manager.destroy_session(second_session_id)
    
    async def test_complex_data_structures(self):
        """Test handling of more complex R data structures."""
        code = """
        # Create a data frame
        df <- data.frame(
            name = c("Alice", "Bob", "Charlie"),
            age = c(25, 30, 35),
            score = c(90, 85, 95)
        )
        
        # Calculate some statistics
        mean_age <- mean(df$age)
        max_score <- max(df$score)
        
        # Return a list with results
        list(
            data = df,
            stats = list(mean_age = mean_age, max_score = max_score)
        )
        """
        result = await self.session_manager.execute_in_session(self.test_session_id, code)
        
        self.assertExecutionSuccess(result) # Check base success first
        output = cast(str, result["successful_output"]) # Cast is safe due to helper
        # Check that specific elements are present in the output string
        self.assertIn("name", output)
        self.assertIn("Alice", output)
        self.assertIn("age", output)
        self.assertIn("score", output)
        self.assertIn("mean_age", output)
        self.assertIn("30", output) # Mean age
        self.assertIn("max_score", output)
        self.assertIn("95", output) # Max score
    
    async def test_concurrent_interleaved_execution(self):
        """Test multiple sessions with interleaved commands executing concurrently."""
        # Create three sessions concurrently
        session_ids = ["session_1", "session_2", "session_3"]
        await asyncio.gather(*(self.session_manager.create_session(sid) for sid in session_ids))
        
        try:
            async def session_task(session_id: str, base_value: int) -> ExecutionResult:
                """Run a sequence of commands and return the final result."""
                # Step 1: Initialize a counter variable
                await self.session_manager.execute_in_session(
                    session_id, f"counter <- {base_value}"
                )
                
                # Step 2: Create a data frame specific to this session
                await self.session_manager.execute_in_session(
                    session_id, 
                    f"""
                    df <- data.frame(
                        id = c(1, 2, 3),
                        value = c({base_value}, {base_value+1}, {base_value+2})
                    )
                    """
                )
                
                # Step 3: Perform a calculation
                await self.session_manager.execute_in_session(
                    session_id, "counter <- counter + sum(df$value)"
                )
                
                # Step 4: Return the final result
                return await self.session_manager.execute_in_session(
                    session_id, "counter"
                )
            
            # Run all session tasks concurrently
            tasks = [
                session_task("session_1", 100),
                session_task("session_2", 200),
                session_task("session_3", 300)
            ]
            final_results = await asyncio.gather(*tasks)
            
            # Verify results for each session
            expected_values = [
                "403",  # Session 1: 100 + (100+101+102)
                "803",  # Session 2: 200 + (200+201+202)
                "1203"  # Session 3: 300 + (300+301+302)
            ]
            
            for i, final_result in enumerate(final_results):
                self.assertExecutionSuccess(final_result, expected_output_substring=expected_values[i])
        
        finally:
            # Clean up all sessions concurrently
            await asyncio.gather(*(self.session_manager.destroy_session(sid) for sid in session_ids))


if __name__ == "__main__":
    unittest.main() 