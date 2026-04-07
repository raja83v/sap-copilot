"""Entry point for running the gateway server."""

import sys
import asyncio

# Must be set BEFORE uvicorn imports/creates any event loop.
# asyncio.create_subprocess_exec() requires ProactorEventLoop on Windows;
# watchfiles-based --reload resets the loop policy, breaking subprocess spawning.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

from .config import settings


def main():
    uvicorn.run(
        "gateway:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        loop="asyncio",  # Forces ProactorEventLoop on Windows via DefaultEventLoopPolicy
    )


if __name__ == "__main__":
    main()
