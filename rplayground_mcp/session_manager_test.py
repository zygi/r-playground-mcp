#!/usr/bin/env python3

import asyncio
import unittest
from typing import List, cast

from session_manager import SessionManager, ExecutionResult


class TestSessionManager(unittest.IsolatedAsyncioTestCase):
    """Test the SessionManager and AsyncRSession classes."""
    
    async def asyncSetUp(self):
        """Set up a session manager and create a test session before each test."""
        self.session_manager = SessionManager()
        self.test_session_id = "test_session"
        await self.session_manager.create_session(self.test_session_id)
    
    async def asyncTearDown(self):
        """Clean up sessions after each test."""
        await self.session_manager.destroy_session(self.test_session_id)
    
    async def test_basic_r_execution(self):
        """Test executing a simple R command and getting the result."""
        code = "1 + 1"
        result = await self.session_manager.execute_in_session(self.test_session_id, code)
        
        self.assertIsNotNone(result["successful_output"])
        self.assertIsNone(result["r_error_output"])
        self.assertIsNone(result["system_error_output"])
        if result["successful_output"]:  # Only check if not None
            self.assertIn("2", result["successful_output"])
    
    async def test_r_error_handling(self):
        """Test that R errors are properly caught and reported."""
        code = "non_existent_variable"
        result = await self.session_manager.execute_in_session(self.test_session_id, code)
        
        self.assertIsNone(result["successful_output"])
        self.assertIsNotNone(result["r_error_output"])
        self.assertIsNone(result["system_error_output"])
        if result["r_error_output"]:  # Only check if not None
            self.assertIn("not found", result["r_error_output"].lower())
    
    async def test_console_output_capture(self):
        """Test that console output is properly captured."""
        code = """
        cat("Hello from R!\\n")
        print("This is a test message")
        """
        result = await self.session_manager.execute_in_session(self.test_session_id, code)
        
        self.assertIsNotNone(result["successful_output"])
        self.assertIsNone(result["r_error_output"])
        self.assertIsNone(result["system_error_output"])
        if result["successful_output"]:  # Only check if not None
            self.assertIn("Hello from R!", result["successful_output"])
            self.assertIn("This is a test message", result["successful_output"])
    
    async def test_session_persistence(self):
        """Test that variables persist within a session."""
        # Set a variable
        code1 = "x <- 42"
        await self.session_manager.execute_in_session(self.test_session_id, code1)
        
        # Use the variable in a subsequent command
        code2 = "x * 2"
        result = await self.session_manager.execute_in_session(self.test_session_id, code2)
        
        self.assertIsNotNone(result["successful_output"])
        if result["successful_output"]:  # Only check if not None
            self.assertIn("84", result["successful_output"])
    
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
            
            self.assertIsNotNone(result1["successful_output"])
            self.assertIsNotNone(result2["successful_output"])
            if result1["successful_output"] and result2["successful_output"]:  # Only check if not None
                self.assertIn("100", result1["successful_output"])
                self.assertIn("200", result2["successful_output"])
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
        
        self.assertIsNotNone(result["successful_output"])
        if result["successful_output"]:  # Only check if not None
            output = result["successful_output"]
            # Check that data frame was printed correctly
            self.assertIn("name", output)
            self.assertIn("age", output)
            self.assertIn("score", output)
            # Check that statistics are included
            self.assertIn("mean_age", output)
            self.assertIn("max_score", output)
            
    async def test_concurrent_interleaved_execution(self):
        """Test multiple sessions with interleaved commands executing concurrently."""
        # Create three sessions
        session_ids = ["session_1", "session_2", "session_3"]
        for session_id in session_ids:
            await self.session_manager.create_session(session_id)
        
        try:
            # Prepare tasks for interleaved execution
            async def session_task(session_id: str, base_value: int):
                """Run a sequence of commands in a specific session."""
                results = []
                
                # Step 1: Initialize a counter variable
                result1 = await self.session_manager.execute_in_session(
                    session_id, f"counter <- {base_value}"
                )
                results.append(result1)
                
                # Step 2: Create a data frame specific to this session
                result2 = await self.session_manager.execute_in_session(
                    session_id, 
                    f"""
                    df <- data.frame(
                        id = c(1, 2, 3),
                        value = c({base_value}, {base_value+1}, {base_value+2})
                    )
                    """
                )
                results.append(result2)
                
                # Step 3: Perform a calculation
                result3 = await self.session_manager.execute_in_session(
                    session_id, "counter <- counter + sum(df$value)"
                )
                results.append(result3)
                
                # Step 4: Return the final result
                result4 = await self.session_manager.execute_in_session(
                    session_id, "counter"
                )
                results.append(result4)
                
                return results
            
            # Run all session tasks concurrently
            tasks = [
                session_task("session_1", 100),
                session_task("session_2", 200),
                session_task("session_3", 300)
            ]
            session_results = await asyncio.gather(*tasks)
            
            # Verify results for each session
            expected_values = [
                # For session 1: 100 + (100+101+102) = 403
                "403",
                # For session 2: 200 + (200+201+202) = 803
                "803",
                # For session 3: 300 + (300+301+302) = 1203
                "1203"
            ]
            
            for i, results in enumerate(session_results):
                # Check the final result of each session
                final_result = results[3]  # The fourth result
                self.assertIsNotNone(final_result["successful_output"])
                if final_result["successful_output"]:
                    self.assertIn(expected_values[i], final_result["successful_output"])
        
        finally:
            # Clean up all sessions
            for session_id in session_ids:
                await self.session_manager.destroy_session(session_id)


if __name__ == "__main__":
    unittest.main() 