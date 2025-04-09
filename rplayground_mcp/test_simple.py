#!/usr/bin/env python3

import sys
from anyio import run
from session_manager import SessionManager

async def main():
    """Simple test for the SessionManager."""
    print("Creating SessionManager...")
    manager = SessionManager()
    
    print("Creating R session...")
    session_id = "test-session"
    await manager.create_session(session_id)
    
    try:
        print("\nTesting basic calculation:")
        result = await manager.execute_in_session(session_id, "1 + 1")
        print(f"Result successful_output: {result['successful_output']}")
        print(f"Result r_error_output: {result['r_error_output']}")
        print(f"Result system_error_output: {result['system_error_output']}")
        
        print("\nTesting variable setting:")
        await manager.execute_in_session(session_id, "x <- 42")
        result = await manager.execute_in_session(session_id, "x * 2")
        print(f"Result successful_output: {result['successful_output']}")
        
        print("\nTesting error handling:")
        result = await manager.execute_in_session(session_id, "non_existent_variable")
        print(f"Result r_error_output: {result['r_error_output']}")
        
        print("\nTesting complex output:")
        code = """
        # Create a data frame
        df <- data.frame(
            name = c("Alice", "Bob", "Charlie"),
            age = c(25, 30, 35),
            score = c(90, 85, 95)
        )
        
        # Print the data frame
        print(df)
        
        # Calculate some statistics
        mean_age <- mean(df$age)
        cat("Mean age:", mean_age, "\\n")
        
        # Return the data frame
        df
        """
        result = await manager.execute_in_session(session_id, code)
        print(f"Complex output:\n{result['successful_output']}")
        
        print("\nAll tests completed!")
        return True
    finally:
        print("\nDestroying session...")
        await manager.destroy_session(session_id)


if __name__ == "__main__":
    try:
        run(main)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1) 