import asyncio
import websockets
from websockets.server import WebSocketServerProtocol

connected = set()


async def broadcast(data, exclude: WebSocketServerProtocol):
    if len(connected) > 1:
        await asyncio.wait([asyncio.create_task(user.send(data)) for user in connected if user is not exclude])


async def sharing_server(websocket, path):
    connected.add(websocket)
    try:
        while True:
            data = await websocket.recv()
            await broadcast(data, websocket)
    finally:
        connected.remove(websocket)


start_server = websockets.serve(sharing_server, "0.0.0.0", 8765)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
