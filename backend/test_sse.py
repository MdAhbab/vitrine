import asyncio
from sse_starlette.sse import ServerSentEvent
import json

async def main():
    event = ServerSentEvent(**{'data': '{"text": "hello\\nworld"}'})
    print(repr(event.encode()))

asyncio.run(main())
