# R Playground MCP

A Python-based interface for executing R code in isolated sessions.

## Features

- Execute R code in isolated sessions
- Capture both text output and return values
- **Plot Support**: Create and retrieve plots from R sessions
- Error handling for both R runtime errors and parsing errors
- Asynchronous API

## Using Plot Functionality

The R session manager now supports creating and capturing plots. Here's how to use it:

### Creating Plots in R

When working within an R session, use the following pattern to create plots:

```r
# Get a unique file name for your plot
filename <- get_img_dest_file_name()

# Create a PNG device with dimensions
png(filename=filename, width=800, height=600)

# Create your plot
plot(1:10, main="My Plot")

# Close the device to save the file
dev.off()
```

### Retrieving Plots in Python

The `ExecutionResult` returned by `execute_in_session()` now includes an `images` field containing a list of PIL.Image objects:

```python
result = await manager.execute_in_session(session_id, r_code)

# Check if any images were created
if result["images"]:
    # Save the first image to a file
    result["images"][0].save("my_plot.png")
    
    # Or process the images directly
    for img in result["images"]:
        # Do something with each image
        process_image(img)
```

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/r-playground-mcp.git
cd r-playground-mcp

# Install using uv
uv venv
source .venv/bin/activate
uv install -e .
```

## Requirements

- Python 3.10+
- rpy2
- PIL (Pillow)
