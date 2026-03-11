from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging
import json
from app.orchestrator.agent import FluentlyAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Fluently Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = FluentlyAgent()

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Fluently Backend"}

@app.websocket("/ws")
async def process_live_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to Fluently Orchestrator websocket.")
    
    try:
        # Wait for the first message which may contain system instructions
        first_msg = await websocket.receive_text()
        system_instructions = None
        try:
            data = json.loads(first_msg)
            if data.get('type') == 'system_instructions':
                system_instructions = data.get('data')
                logger.info(f"Received custom system instructions from client")
        except json.JSONDecodeError:
            pass
        
        await agent.run_session(websocket, system_instructions=system_instructions)
    except WebSocketDisconnect:
        logger.info("Client disconnected.")
    except Exception as e:
        logger.error(f"Error in websocket loop: {e}")
