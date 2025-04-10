import asyncio

from rplayground_mcp.configuration import Configuration
from .session_manager import SessionManager
import sys
import logging

sm = SessionManager(Configuration())
arg = sys.argv[1]


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

async def main():
    id = await sm.create_session()
    print(f"Created session {id}")
    result = await sm.execute_in_session(id, arg)
    print(f"Result: {result}")
    await sm.destroy_session(id)
    print(f"Destroyed session {id}")

def run():
    print("Starting main")
    asyncio.run(main())

if __name__ == "__main__":
    run()
