import asyncio
from backend.ai.agents.concierge import stream
from backend.shared.models import Listing

async def main():
    async for chunk in stream("React dashboard"):
        print(chunk)

asyncio.run(main())
