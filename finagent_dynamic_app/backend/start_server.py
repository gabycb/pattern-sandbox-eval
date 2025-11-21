"""
Startup script for the FastAPI backend with proper Windows event loop configuration.

This script sets the Windows event loop policy before uvicorn creates its loop,
ensuring compatibility with aiodns used by CosmosDB and Azure credentials.
"""
import asyncio
import sys

# CRITICAL: Set event loop policy BEFORE uvicorn imports
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print("Set WindowsSelectorEventLoopPolicy for aiodns compatibility")

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Set to True for development
        log_level="info"
    )
