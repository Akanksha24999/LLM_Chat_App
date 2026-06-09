from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, status
from typing import Dict, Union
import json
import os
import asyncio
from datetime import datetime
from fastapi.responses import FileResponse
import google.generativeai as genai
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import redis
from prometheus_fastapi_instrumentator import Instrumentator

load_dotenv()

# Redis Setup
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Database Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/chatdb")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ChatLog(Base):
    __tablename__ = "chat_logs"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    sender = Column(String)
    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Instrument the app with Prometheus
Instrumentator().instrument(app).expose(app)

@app.get("/health")
async def health_check(response: Response):
    health_status = {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    is_healthy = True

    try:
        # Check Postgres
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        health_status["database"] = "up"
    except Exception as e:
        health_status["database"] = f"down: {str(e)}"
        is_healthy = False

    try:
        # Check Redis
        redis_client.ping()
        health_status["redis"] = "up"
    except Exception as e:
        health_status["redis"] = f"down: {str(e)}"
        is_healthy = False

    if not is_healthy:
        health_status["status"] = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return health_status

def save_chat_log(session_id: str, sender: str, message: str):
    db = SessionLocal()
    try:
        log = ChatLog(session_id=session_id, sender=sender, message=message)
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Error saving chat log: {e}")
    finally:
        db.close()

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Instruction for the AI model
SYSTEM_INSTRUCTION = "You are an expert career counselor and guide for job seekers. Help them with resumes, interview preparation, career advice, and navigating the job market. Keep responses concise and helpful."

@app.get("/")
async def get():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_path = os.path.join(base_dir, "frontend", "index.html")
    return FileResponse(index_path)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

class ConnectionManager:
    def __init__(self):
        # Map each WebSocket to its own Gemini ChatSession and session info
        self.active_connections: Dict[WebSocket, Dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        # Create a unique session ID for this connection
        session_id = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + str(id(websocket))
        
        # Initialize Gemini Model and Chat Session for this connection
        model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",
            system_instruction=SYSTEM_INSTRUCTION
        )
        chat_session = model.start_chat()
        
        self.active_connections[websocket] = {
            "session": chat_session,
            "id": session_id
        }
        
        welcome_msg = "Hello! I am your AI Career Guide. How can I help you with your job search today?"
        await self.send_system_message("Connected to AI Career Guide.", websocket)
        await self.send_ai_message(welcome_msg, websocket)
        save_chat_log(session_id, "AI", welcome_msg)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def send_system_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(json.dumps({
            "type": "system", 
            "message": message
        }))

    async def send_ai_message(self, message: str, websocket: WebSocket):
        cur_time = datetime.now().strftime("%I:%M:%S %p")
        await websocket.send_text(json.dumps({
            "type": "chat",
            "username": "Career Guide AI",
            "message": message,
            "time": cur_time,
            "isSelf": False
        }))

    async def send_user_message_echo(self, message: str, websocket: WebSocket):
        cur_time = datetime.now().strftime("%I:%M:%S %p")
        await websocket.send_text(json.dumps({
            "type": "chat",
            "username": "You",
            "message": message,
            "time": cur_time,
            "isSelf": True
        }))

    async def get_ai_response(self, message: str, websocket: WebSocket):
        conn_data = self.active_connections.get(websocket)
        if not conn_data:
            return

        chat_session = conn_data["session"]
        session_id = conn_data["id"]

        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                response = await chat_session.send_message_async(message)
                await self.send_ai_message(response.text, websocket)
                save_chat_log(session_id, "AI", response.text)
                return 
            except Exception as e:
                error_str = str(e)
                if "429" in error_str:
                    if attempt < max_retries - 1:
                        await self.send_system_message(f"Rate limit hit. Retrying in {retry_delay} seconds...", websocket)
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        await self.send_system_message("Rate limit reached. Please wait a minute before sending more messages.", websocket)
                else:
                    await self.send_system_message(f"Error getting AI response: {error_str}", websocket)
                    break

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Log user message
            session_id = manager.active_connections[websocket]["id"]
            save_chat_log(session_id, "User", data)
            
            # Echo the user's message back to display it
            await manager.send_user_message_echo(data, websocket)
            # Forward the message to Gemini and return the response
            await manager.get_ai_response(data, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
