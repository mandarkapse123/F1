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
        logging.info("Client connected.")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

# --- 20-CAR GHOST SIMULATOR ---
class GhostCar:
    def __init__(self, driver_no, team_id, base_speed, start_distance):
        self.no = driver_no
        self.team = team_id
        self.speed = base_speed
        self.gear = 8
        self.throttle = 100
        self.brake = 0
        self.is_braking = False
        self.corner_timer = 0
        self.lap = 1
        self.distance = start_distance 
        self.track_length = 5400.0 # Average track length in meters

    def update(self):
        # Simulate Driving Physics
        if self.corner_timer > 0:
            self.corner_timer -= 1
            if self.is_braking:
                self.speed = max(90, self.speed - random.randint(15, 30))
                self.gear = max(2, self.gear - 1 if self.speed % 40 == 0 else self.gear)
                self.throttle = 0
                self.brake = random.randint(60, 100)
            else: 
                self.speed = min(320, self.speed + random.randint(10, 20))
                self.gear = min(8, self.gear + 1 if self.speed % 35 == 0 else self.gear)
                self.throttle = random.randint(80, 100)
                self.brake = 0
        else:
            if random.random() < 0.04: 
                self.is_braking = True
                self.corner_timer = random.randint(3, 5) 
            elif self.is_braking:
                self.is_braking = False
                self.corner_timer = random.randint(4, 8) 
            else:
                self.speed = min(335, self.speed + random.randint(-2, 5))
                self.gear = 8
                self.throttle = 100
                self.brake = 0
                
        # Calculate Position
        speed_ms = self.speed / 3.6
        self.distance += speed_ms * 0.25
        
        if self.distance >= self.track_length:
            self.distance -= self.track_length
            self.lap += 1
            
        return {
            "no": self.no,
            "team": self.team,
            "speed": self.speed, 
            "gear": self.gear, 
            "throttle": self.throttle, 
            "brake": self.brake,
            "lap": self.lap,
            "progress": self.distance / self.track_length
        }

# Generate the 2026 Grid spaced out around the track
GRID = [
    ("1", "redbull", 312, 5000), ("11", "redbull", 310, 4800),
    ("4", "mclaren", 311, 4600), ("81", "mclaren", 309, 4400),
    ("16", "ferrari", 311, 4200), ("44", "ferrari", 310, 4000),
    ("63", "mercedes", 308, 3800), ("12", "mercedes", 307, 3600),
    ("14", "aston", 305, 3400), ("18", "aston", 304, 3200),
    ("10", "alpine", 302, 3000), ("31", "alpine", 301, 2800),
    ("23", "williams", 303, 2600), ("2", "williams", 300, 2400),
    ("22", "racingbulls", 303, 2200), ("3", "racingbulls", 301, 2000),
    ("77", "sauber", 298, 1800), ("24", "sauber", 297, 1600),
    ("20", "haas", 299, 1400), ("27", "haas", 298, 1200)
]

cars = [GhostCar(no, team, spd, dist) for no, team, spd, dist in GRID]

async def telemetry_stream():
    while True:
        if len(manager.active_connections) > 0:
            car_data = {car.no: car.update() for car in cars}
            await manager.broadcast(json.dumps({"type": "telemetry", "data": car_data}))
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
