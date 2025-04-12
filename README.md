# MCP R Playground
[![PyPI version](https://img.shields.io/pypi/v/rplayground-mcp.svg)](https://pypi.org/project/rplayground-mcp/)

An MCP server that allows AI models to execute R code, see its results, and draw and observe plots. 
It can be used for sophisticated agentic deployments, but also as a way to augment AI clients like Claude Desktop when talking to them about scientific papers. 

## Features:
- Stateful sessions: each conversation thread gets a new session, but the session can persist across calss and user/assistant interactions. 
- Graphics output: multimodal models can draw plots using standard R libraries like ggplot, see those plots, and react to them.
- __NO HOST ISOLATION__: while each session runs as a separate R environment, they have access to global dependencies and all files on the computer. While unlikely, a rogue model could write R code that deletes your important files.
- Works in all common operating systems/architectures - Windows x64 / arm64, MacOS, Linux 


## Configuration
Currently there's just one configuration parameter that can be set as an environment variable:
- `RPLAYGROUND_MCP_SUPPORT_IMAGE_OUTPUT`, default True. If set to False, image output will be disabled, and tool descriptions will be made to reflect that.


## Installation
Basic instructions for technical users:
1) Have R installed, and the R_HOME environment variable set
2) Have a recent version of the `uv` installed
3) run `uvx --python=3.13 rplayground-mcp`, and it should just work.

## Detailed Installation
This section is for less technical users who want to set up this MCP to use with Claude Desktop or similar AI user interfaces that support MCP extensions.

### Windows
- Make sure you've set up Claude Desktop to create the MCP configuration file by following instructions here: https://modelcontextprotocol.io/quickstart/user
- Make sure you have R installed. The recommended source is here https://cran.rstudio.com/ .
- Make sure you have `uv` installed. `uv` is the project management tool for Python, the programming language this tool is written in. More detailed instructions can be found here https://docs.astral.sh/uv/getting-started/installation/#pypi, we provide the instructions for the most straightforward method:
    1) Open the Terminal app
    2) In the terminal, paste in the following installation command: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
    3) Close the Terminal app and reopen it
    4) type in `uv` and confirm you don't see any red errors.
- We have provided a helper script that you can use to set up the MCP server to work with Claude Desktop. You can run it with `uv run --python=3.13 https://raw.githubusercontent.com/zygi/r-playground-mcp/refs/heads/master/scripts/setup_helper.py`. With your permission, it will:
    - Set the R_HOME environment variable to your R installation
    - Install the MCP inside your Claude Desktop configuration.
- That's it! Starting Claude Desktop should now display the tools as available. Or just ask it to "test out the `execute_r_command` tool".


### MacOS
- Make sure you've set up Claude Desktop to create the MCP configuration file by following instructions here: https://modelcontextprotocol.io/quickstart/user
- Make sure you have R installed. The recommended source is here https://cran.rstudio.com/ .
- Make sure you have `uv` installed. `uv` is the project management tool for Python, the programming language this tool is written in. More detailed instructions can be found here https://docs.astral.sh/uv/getting-started/installation/#pypi, we provide the instructions for the most straightforward method:
    1) Open the Terminal app
    2) In the terminal, paste in the following installation command: `curl -LsSf https://astral.sh/uv/install.sh | sh`
    3) Close the Terminal app and reopen it
    4) type in `uv` and confirm you don't see any red errors.
- We have provided a helper script that you can use to set up the MCP server to work with Claude Desktop. You can run it with `uv run --python=3.13 https://raw.githubusercontent.com/zygi/r-playground-mcp/refs/heads/master/scripts/setup_helper.py`. With your permission, it will:
    - Set the R_HOME environment variable to your R installation
    - Install the MCP inside your Claude Desktop configuration.
- That's it! Starting Claude Desktop should now display the tools as available. Or just ask it to "test out the `execute_r_command` tool".

## Issues and Contributions
Feel free to create an Issue if you have questions or requests. Small PRs are welcome anytime, larger PRs should be discussed by creating an Issue before a PR is started. 


