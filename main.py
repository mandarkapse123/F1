import asyncio
import json
import random
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
# from fastf1.livetiming.client import SignalRClient # Used for the real stream

app = FastAPI()
logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logging.info("Client disconnected.")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

# --- GHOST MODE: Realistic Telemetry Simulator ---
# This runs when the actual F1 servers are offline (Monday - Thursday)
class GhostCar:
    def __init__(self, driver_no, base_speed):
        self.no = driver_no
        self.speed = base_speed
        self.gear = 8
        self.throttle = 100
        self.brake = 0
        self.is_braking = False
        self.corner_timer = 0

    def update(self):
        if self.corner_timer > 0:
            self.corner_timer -= 1
            if self.is_braking:
                self.speed = max(80, self.speed - random.randint(15, 30))
                self.gear = max(2, self.gear - 1 if self.speed % 40 == 0 else self.gear)
                self.throttle = 0
                self.brake = random.randint(60, 100)
            else: # Accelerating out of corner
                self.speed = min(320, self.speed + random.randint(10, 20))
                self.gear = min(8, self.gear + 1 if self.speed % 35 == 0 else self.gear)
                self.throttle = random.randint(80, 100)
                self.brake = 0
        else:
            # Randomly approach a corner
            if random.random() < 0.05: 
                self.is_braking = True
                self.corner_timer = random.randint(3, 6) # Time spent braking
            elif self.is_braking:
                self.is_braking = False
                self.corner_timer = random.randint(5, 10) # Time spent accelerating
            else:
                # Flat out on a straight
                self.speed = min(330, self.speed + random.randint(-2, 5))
                self.gear = 8
                self.throttle = 100
                self.brake = 0
        
        return {"speed": self.speed, "gear": self.gear, "throttle": self.throttle, "brake": self.brake}

async def telemetry_stream():
    """
    On race weekends, this function intercepts the FastF1 SignalR stream.
    If no session is active, it defaults to the GhostCars to keep the UI alive.
    """
    hamilton = GhostCar("44", 310)
    leclerc = GhostCar("16", 308)
    
    while True:
        if len(manager.active_connections) > 0:
            
            # TODO: During a live race, replace this ghost data with parsed 
            # 'CarData.z' packets from the FastF1 SignalRClient.
            payload = {
                "type": "telemetry",
                "data": {
                    "44": hamilton.update(),
                    "16": leclerc.update()
                }
            }
            await manager.broadcast(json.dumps(payload))
            
        # Telemetry broadcasts roughly every 250ms
        await asyncio.sleep(0.25)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(telemetry_stream())

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
