import asyncio
import json
import random
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

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

class GhostCar:
    def __init__(self, driver_no, base_speed, start_distance=0.0):
        self.no = driver_no
        self.speed = base_speed
        self.gear = 8
        self.throttle = 100
        self.brake = 0
        self.is_braking = False
        self.corner_timer = 0
        
        # --- NEW: Positional Tracking ---
        self.lap = 1
        self.distance = start_distance 
        self.track_length = 5793.0 # Approx length of Monza in meters

    def update(self):
        # 1. Calculate Speed & Gear changes (Braking/Accelerating)
        if self.corner_timer > 0:
            self.corner_timer -= 1
            if self.is_braking:
                self.speed = max(80, self.speed - random.randint(15, 30))
                self.gear = max(2, self.gear - 1 if self.speed % 40 == 0 else self.gear)
                self.throttle = 0
                self.brake = random.randint(60, 100)
            else: 
                self.speed = min(320, self.speed + random.randint(10, 20))
                self.gear = min(8, self.gear + 1 if self.speed % 35 == 0 else self.gear)
                self.throttle = random.randint(80, 100)
                self.brake = 0
        else:
            if random.random() < 0.05: 
                self.is_braking = True
                self.corner_timer = random.randint(3, 6) 
            elif self.is_braking:
                self.is_braking = False
                self.corner_timer = random.randint(5, 10) 
            else:
                self.speed = min(330, self.speed + random.randint(-2, 5))
                self.gear = 8
                self.throttle = 100
                self.brake = 0
                
        # 2. Calculate Distance Traveled (Speed in m/s * 0.25 seconds)
        speed_ms = self.speed / 3.6
        distance_moved = speed_ms * 0.25
        self.distance += distance_moved
        
        # 3. Handle Lap Completion
        if self.distance >= self.track_length:
            self.distance -= self.track_length
            self.lap += 1
            
        # 4. Calculate Lap Percentage (0.0 to 1.0)
        progress = self.distance / self.track_length
        
        return {
            "speed": self.speed, 
            "gear": self.gear, 
            "throttle": self.throttle, 
            "brake": self.brake,
            "lap": self.lap,
            "progress": progress
        }

async def telemetry_stream():
    # Start Leclerc 200 meters ahead of Hamilton so we can see them chasing
    hamilton = GhostCar("44", 310, 0.0)
    leclerc = GhostCar("16", 308, 200.0)
    
    while True:
        if len(manager.active_connections) > 0:
            payload = {
                "type": "telemetry",
                "data": {
                    "44": hamilton.update(),
                    "16": leclerc.update()
                }
            }
            await manager.broadcast(json.dumps(payload))
            
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
