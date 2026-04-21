import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastf1.livetiming.client import SignalRClient

app = FastAPI()

# Allow your frontend HTML file to connect to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manage active WebSocket connections to your frontend
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

# The F1 Live Timing background task
async def f1_live_telemetry_stream():
    """
    Hooks into the official F1 SignalR stream.
    In a full production app, you would subclass SignalRClient to capture
    the messages in memory and broadcast them, rather than writing to a file.
    """
    # NOTE: FastF1's default client writes to a file. For a live web app,
    # you typically parse the stream output directly. 
    # This is a simplified async loop to simulate sending that parsed data.
    
    while True:
        if len(manager.active_connections) > 0:
            # Simulated telemetry payload structure you would extract from the SignalR stream
            payload = {
                "type": "telemetry",
                "data": {
                    "44": {"speed": 315, "gear": 8, "throttle": 100, "brake": 0},
                    "16": {"speed": 312, "gear": 8, "throttle": 100, "brake": 0}
                }
            }
            await manager.broadcast(json.dumps(payload))
        
        # F1 telemetry updates roughly every 250ms
        await asyncio.sleep(0.25)

@app.on_event("startup")
async def startup_event():
    # Start the F1 telemetry stream in the background when the server boots
    asyncio.create_task(f1_live_telemetry_stream())

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# To run locally: uvicorn main:app --reload
