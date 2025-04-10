import asyncio
from .session_manager import SessionManager
import sys

if __name__ == "__main__":
    sm = SessionManager()
    arg = sys.argv[1]
    
    import logging
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        id = await sm.create_session()
        print(f"Created session {id}")
        result = await sm.execute_in_session(id, arg)
        print(f"Result: {result}")
        await sm.destroy_session(id)
        print(f"Destroyed session {id}")

    asyncio.run(main())
