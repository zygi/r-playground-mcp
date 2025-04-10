import asyncio
import sys
import os
import pytest

# Add the parent directory to the path so we can import the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rplayground_mcp.session_manager import SessionManager

@pytest.mark.asyncio
async def test_r_plotting():
    """
    Test the R plotting functionality.
    
    This demonstrates how to:
    1. Create an R session
    2. Generate a plot in R
    3. Retrieve the plot image from Python
    """
    manager = SessionManager()
    
    try:
        # Create a new session
        session_id = await manager.create_session()
        print(f"Created session: {session_id}")
        
        # Basic R plot example
        plot_code = """
        # Get the file name for our plot
        filename <- get_img_dest_file_name()
        
        # Create a PNG device explicitly with dimensions
        png(filename=filename, width=800, height=600)
        
        # Create a simple plot
        plot(1:10, main="Simple Line Plot")
        
        # Close the device to save the file
        dev.off()
        
        # Return the filename
        filename
        """
        
        result = await manager.execute_in_session(session_id, plot_code)
        
        # Print the outputs
        if result["successful_output"]:
            print(f"R output: {result['successful_output']}")
        
        if result["r_error_output"]:
            print(f"R error: {result['r_error_output']}")
            
        if result["system_error_output"]:
            print(f"System error: {result['system_error_output']}")
        
        # Check if we have images
        print(f"Number of images captured: {len(result['images'])}")
        assert result["images"]
        assert result["images"][0].size != (0, 0)
        
    finally:
        # Clean up
        await manager.destroy()

if __name__ == "__main__":
    asyncio.run(test_r_plotting()) 