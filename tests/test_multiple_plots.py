import asyncio
import sys
import os
import time
import pytest

# Add the parent directory to the path so we can import the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rplayground_mcp.session_manager import SessionManager

@pytest.mark.asyncio
async def test_multiple_plots():
    """
    Test creating multiple plots in a single R session.
    """
    manager = SessionManager()
    
    try:
        # Create a new session
        session_id = await manager.create_session()
        print(f"Created session: {session_id}")
        
        # First, let's create a more complex dataset
        setup_code = """
        # Create a sample dataset
        set.seed(123)
        x <- 1:50
        y1 <- 2*x + rnorm(50, mean=0, sd=10)
        y2 <- 3*x + rnorm(50, mean=5, sd=15)
        df <- data.frame(x=x, y1=y1, y2=y2)
        
        # Return a confirmation
        "Dataset created"
        """
        
        result = await manager.execute_in_session(session_id, setup_code)
        print(f"Setup result: {result['successful_output']}")
        
        # Now create a scatter plot
        scatter_code = """
        # Create a scatter plot
        png(filename=get_img_dest_file_name(), width=800, height=600)
        plot(df$x, df$y1, main="Scatter Plot", 
             xlab="X Values", ylab="Y Values",
             col="blue", pch=19)
        dev.off()
        
        "Scatter plot created"
        """
        
        result = await manager.execute_in_session(session_id, scatter_code)
        print(f"Scatter plot result: {result['successful_output']}")
        print(f"Images captured: {len(result['images'])}")
        assert result["images"]
        assert result["images"][0].size != (0, 0)
        
        # Now create a bar plot
        bar_code = """
        # Create a bar plot
        png(filename=get_img_dest_file_name(), width=800, height=600)
        barplot(df$y2[1:10], names.arg=df$x[1:10], 
                main="Bar Plot", xlab="X Values", ylab="Y2 Values",
                col="green")
        dev.off()
        
        "Bar plot created"
        """
        
        result = await manager.execute_in_session(session_id, bar_code)
        print(f"Bar plot result: {result['successful_output']}")
        print(f"Images captured: {len(result['images'])}")
        assert result["images"]
        assert result["images"][0].size != (0, 0)
        
        # Finally, create a histogram
        hist_code = """
        # Create a histogram
        png(filename=get_img_dest_file_name(), width=800, height=600)
        hist(df$y1, main="Histogram", xlab="Y1 Values",
             col="purple", breaks=15)
        dev.off()
        
        "Histogram created"
        """
        
        result = await manager.execute_in_session(session_id, hist_code)
        print(f"Histogram result: {result['successful_output']}")
        print(f"Images captured: {len(result['images'])}")
        assert result["images"]
        assert result["images"][0].size != (0, 0)
        
    finally:
        # Clean up
        await manager.destroy()

if __name__ == "__main__":
    asyncio.run(test_multiple_plots()) 