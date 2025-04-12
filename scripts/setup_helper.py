# /// script
# dependencies = [
#   "packaging",
# ]
# ///

import os
import sys
import shutil
from typing import Optional, Dict, Any
import string  # Added import
import re  # Added import
from packaging import version  # Added import for version parsing
import subprocess  # Added import
import json  # Added import
from pathlib import Path  # Added import


def _is_valid_r_home(path: str) -> bool:
    """Check if a given path is a valid R home directory."""
    if not path or not os.path.isdir(path):
        return False
    # Check for a key executable, assuming Windows path structure
    potential_exe_path = os.path.join(path, "bin", "R.exe")
    return os.path.exists(potential_exe_path)


def _find_r_home_windows_heuristic() -> Optional[str]:
    """Heuristically search for R installations in common Windows locations."""
    possible_r_homes = []
    # Get available drive letters
    drive_letters = [
        f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")
    ]

    program_files_dirs = ["Program Files", "Program Files (x86)"]

    for drive in drive_letters:
        for pf_dir in program_files_dirs:
            base_r_path = os.path.join(drive, pf_dir, "R")
            if os.path.isdir(base_r_path):
                try:
                    for item in os.listdir(base_r_path):
                        # Check if item looks like an R version directory (e.g., R-4.3.1)
                        if item.startswith("R-") and os.path.isdir(
                            os.path.join(base_r_path, item)
                        ):
                            potential_r_home = os.path.join(base_r_path, item)
                            if _is_valid_r_home(potential_r_home):
                                # Try to parse version from directory name
                                version_match = re.match(r"R-(\d+\.\d+(\.\d+)?)", item)
                                if version_match:
                                    try:
                                        ver = version.parse(version_match.group(1))
                                        possible_r_homes.append((ver, potential_r_home))
                                    except version.InvalidVersion:
                                        continue  # Ignore directories with unparseable versions
                except OSError:
                    # Ignore errors like permission denied
                    continue

    # Sort found R homes by version (descending) and return the latest valid one
    if possible_r_homes:
        possible_r_homes.sort(key=lambda x: x[0], reverse=True)
        return possible_r_homes[0][1]  # Return the path of the latest version

    return None


def find_r_home() -> Optional[str]:
    """Find the R home directory using environment variables, PATH, and heuristics."""
    # 1. Check R_HOME environment variable first
    r_home_env = os.environ.get("R_HOME")
    if r_home_env and _is_valid_r_home(r_home_env):
        return r_home_env

    # 2. If R_HOME env var is not set or invalid, check PATH for R.exe
    r_exe_path = shutil.which("R")
    if r_exe_path:
        potential_r_home = os.path.dirname(os.path.dirname(r_exe_path))
        # Validate the inferred path
        if _is_valid_r_home(potential_r_home):
            # Check if the R.exe in the inferred R_HOME matches the one found in PATH
            expected_exe_path = os.path.join(potential_r_home, "bin", "R.exe")
            if (
                os.path.normpath(expected_exe_path).lower()
                == os.path.normpath(r_exe_path).lower()
            ):
                return potential_r_home

    # 3. Heuristic check for common install locations
    if sys.platform == "win32":
        heuristic_path = _find_r_home_windows_heuristic()
        if heuristic_path:
            return heuristic_path
    # TODO: Add heuristic check for common install locations on other OS (macOS, Linux)

    return None


def check_uvx_version(required_version_str: str = "0.6") -> None:
    """Checks if the installed uvx version meets the minimum requirement."""
    required_version = version.parse(required_version_str)
    try:
        print(f"Checking uvx version (requires >= {required_version_str})...")
        result = subprocess.run(
            ["uvx", "--version"],
            capture_output=True,
            text=True,
            check=True,
            shell=False,
        )
        # Example output: uvx 0.6.0 (rev 12345)
        output = result.stdout.strip()
        match = re.search(r"^uvx\s+(\d+\.\d+(\.\d+)?)", output)
        if match:
            uvx_version_str = match.group(1)
            uvx_version = version.parse(uvx_version_str)
            print(f"Found uvx version: {uvx_version}")
            if uvx_version < required_version:
                print(
                    f"Error: uvx version {uvx_version} is installed, but version {required_version_str} or higher is required.",
                    file=sys.stderr,
                )
                sys.exit(1)
            else:
                print("uvx version check passed.")
        else:
            print(
                f"Warning: Could not parse uvx version from output: {output}",
                file=sys.stderr,
            )
            # Decide whether to proceed or exit if parsing fails
            # For now, let's proceed with a warning

    except FileNotFoundError:
        print(
            "Error: 'uvx' command not found. Please ensure uv/uvx is installed and in your PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running 'uvx --version': {e}", file=sys.stderr)
        print(f"Command output: {e.stdout}", file=sys.stderr)
        print(f"Command error: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(
            f"An unexpected error occurred during uvx version check: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


def get_claude_config_path() -> Optional[Path]:
    """Gets the OS-specific path to the Claude Desktop config file."""
    try:
        if sys.platform == "win32":
            appdata = os.getenv("APPDATA")
            if not appdata:
                print("Error: APPDATA environment variable not found.", file=sys.stderr)
                return None
            config_path = Path(appdata) / "Claude" / "claude_desktop_config.json"
        elif sys.platform == "darwin":  # macOS
            config_path = (
                Path.home()
                / "Library"
                / "Application Support"
                / "Claude"
                / "claude_desktop_config.json"
            )
        else:
            print(
                f"Warning: Unsupported platform '{sys.platform}' for Claude Desktop config.",
                file=sys.stderr,
            )
            return None
        return config_path
    except Exception as e:
        print(f"Error determining Claude config path: {e}", file=sys.stderr)
        return None


def install_mcp_config_to_claude(mcp_config: Dict[str, Any]) -> None:
    """Installs the generated MCP configuration into the Claude Desktop config file."""
    config_path = get_claude_config_path()
    if not config_path:
        print("Skipping Claude Desktop configuration update.", file=sys.stderr)
        return

    print(f"\nAttempting to update Claude Desktop config at: {config_path}")

    # Ensure the directory exists
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating directory {config_path.parent}: {e}", file=sys.stderr)
        return

    claude_config: Dict[str, Any] = {}
    try:
        if config_path.exists():
            with open(config_path, "r") as f:
                claude_config = json.load(f)
        else:
            print(f"Config file not found at {config_path}. A new one will be created.")
            # Initialize with a basic structure if creating anew
            claude_config = {"mcpServers": {}}

    except json.JSONDecodeError:
        print(
            f"Error: Existing config file at {config_path} is corrupted. Cannot update.",
            file=sys.stderr,
        )
        # Optionally, offer to overwrite or back up the corrupted file
        return
    except OSError as e:
        print(f"Error reading config file {config_path}: {e}", file=sys.stderr)
        return

    # Ensure 'mcpServers' key exists
    if "mcpServers" not in claude_config:
        claude_config["mcpServers"] = {}
    elif not isinstance(claude_config.get("mcpServers"), dict):
        print(
            f"Error: 'mcpServers' key in {config_path} is not a dictionary. Cannot update.",
            file=sys.stderr,
        )
        return  # Or handle differently, e.g., overwrite if confirmed

    # Add or update the 'r-playground' configuration
    # Assuming mcp_config looks like {"r-playground": {...}}
    if "r-playground" in mcp_config:
        claude_config["mcpServers"]["r-playground"] = mcp_config["r-playground"]
        print("Updated 'r-playground' configuration.")
    else:
        print(
            "Warning: Generated MCP config doesn't contain the expected 'r-playground' key.",
            file=sys.stderr,
        )
        return  # Nothing to install if the key isn't there

    # Write the updated config back
    try:
        with open(config_path, "w") as f:
            json.dump(claude_config, f, indent=2)
        print(f"Successfully updated Claude Desktop config at: {config_path}")
    except OSError as e:
        print(f"Error writing updated config file {config_path}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred while writing the config file: {e}", file=sys.stderr)


if __name__ == "__main__":
    # 1. Check uvx version first
    check_uvx_version("0.6")
    print("-" * 20)  # Separator

    # --- Platform Check ---
    if sys.platform != "win32":
        print(
            "This setup helper script currently only provides automatic R_HOME setting for Windows."
        )
        # Optionally, still try to find R_HOME and print it for non-Windows users
        r_home_path = find_r_home()
        if r_home_path:
            print(f"Detected R home directory: {r_home_path}")
            print("Please set the R_HOME environment variable manually if needed.")
        else:
            print("Could not automatically detect the R home directory.")
        sys.exit(0)

    # --- R Home Discovery and Setup (Windows) ---
    print("\nSearching for R installation...")
    current_r_home = os.environ.get("R_HOME")
    found_r_home_path = (
        find_r_home()
    )  # This already prioritizes env var, then PATH, then heuristic

    r_home_to_use = None

    if current_r_home:
        print(f"R_HOME environment variable is already set to: {current_r_home}")
        if _is_valid_r_home(current_r_home):
            print("This appears to be a valid R installation directory.")
            r_home_to_use = current_r_home  # Use the existing valid R_HOME
        else:
            print(
                "Warning: This path does not seem to be a valid R installation (missing bin/R.exe)."
            )
            if (
                found_r_home_path
                and found_r_home_path.lower() != current_r_home.lower()
            ):
                print(
                    f"However, a potentially valid R installation was found at: {found_r_home_path}"
                )
                print(
                    "You might consider updating your R_HOME variable or using the found path."
                )
                # Decide whether to automatically use found_r_home_path or require user action
                # For now, let's prefer the found one if the current one is invalid
                r_home_to_use = found_r_home_path
            else:
                # Current R_HOME is invalid, and we didn't find another one
                print("Cannot proceed without a valid R_HOME.")

    elif found_r_home_path:
        print(f"\nFound a potential R home directory: {found_r_home_path}")
        print("The R_HOME environment variable is not currently set.")

        response = "n"  # Default to no if non-interactive
        try:
            response = (
                input(
                    "Do you want to set R_HOME to this path for your user account? (y/N): "
                )
                .lower()
                .strip()
            )
        except EOFError:  # Handle non-interactive environments
            print("\nNon-interactive mode detected, skipping R_HOME setup.")

        if response in ["y", "yes"]:
            print(f"Setting R_HOME={found_r_home_path} for the current user...")
            try:
                command = ["setx", "R_HOME", found_r_home_path]
                result = subprocess.run(
                    command, capture_output=True, text=True, check=True, shell=False
                )
                print("Successfully set R_HOME.")
                print(
                    "Please note: You may need to restart your terminal or log out/in for the change to take full effect everywhere."
                )
                r_home_to_use = found_r_home_path  # Use the path we just set
            except Exception as e:  # Catching generic exception from setx block
                print(f"Failed to set R_HOME automatically: {e}", file=sys.stderr)
                print(
                    "Proceeding without setting R_HOME, but will use the found path for configuration."
                )
                r_home_to_use = (
                    found_r_home_path  # Still use the path we found for JSON output
                )
        else:
            print("Okay, R_HOME environment variable was not set.")
            print(
                "Will use the found path for configuration output, but it won't be persisted."
            )
            r_home_to_use = found_r_home_path  # Use the path we found for JSON output, even if not set

    else:  # Neither current_r_home nor found_r_home_path is valid/exists
        print(
            "\nR home directory could not be found automatically and R_HOME is not set correctly."
        )
        print("Please ensure R is installed correctly and R_HOME is set.")
        # Cannot generate JSON without R_HOME

    # --- Generate MCP JSON Output ---
    print("-" * 20)  # Separator
    if r_home_to_use:
        print("\nGenerating MCP configuration JSON...")
        mcp_config = {
            "r-playground": {
                "command": "uvx",
                "args": ["--python=3.13", "--refresh-package=rplayground-mcp", "rplayground-mcp"],
                "env": {"R_HOME": r_home_to_use},
            }
        }

        # Print the JSON object
        print(json.dumps(mcp_config, indent=2))

        # --- Ask to Install to Claude Desktop ---
        install_response = "n"  # Default to no if non-interactive
        try:
            if (
                get_claude_config_path()
            ):  # Only ask if we know where the config *should* be
                install_response = (
                    input(
                        "Do you want to install this configuration into Claude Desktop? (y/N): "
                    )
                    .lower()
                    .strip()
                )
        except EOFError:  # Handle non-interactive environments
            print(
                "\nNon-interactive mode detected, skipping Claude Desktop config installation."
            )

        if install_response in ["y", "yes"]:
            install_mcp_config_to_claude(mcp_config)
        else:
            print("Skipping installation to Claude Desktop.")

    else:
        print(
            "\nCould not determine a valid R_HOME path. Skipping MCP JSON generation.",
            file=sys.stderr,
        )
