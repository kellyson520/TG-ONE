from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from core.container import container
from core.pipeline import MessageContext, Pipeline
from middlewares.loader import RuleLoaderMiddleware
from middlewares.dedup import DedupMiddleware
from middlewares.filter import FilterMiddleware
from middlewares.sender import SenderMiddleware
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class SimulationRequest(BaseModel):
    chat_id: int 
    text: Optional[str] = None
    user_id: Optional[int] = None
    sender_id: Optional[int] = None
    media_type: Optional[str] = None
    reply_to_msg_id: Optional[int] = None

class TraceItem(BaseModel):
    step: str
    status: str
    details: Dict[str, Any]
    timestamp: float

@router.post("/simulate")
async def simulate_message(req: SimulationRequest):
    """
    Simulate message processing through the pipeline
    """
    
    # Mock Message Object
    class MockMedia:
        def __init__(self, type_name):
            self.type = type_name
            
    class MockMessage:
        def __init__(self):
            self.id = 999999
            self.text = req.text or ""
            self.date = datetime.utcnow()
            self.media = MockMedia(req.media_type) if req.media_type else None
            self.sender_id = req.sender_id or req.user_id or 123456
            self.grouped_id = None
            self.out = False
            self.reply_to_msg_id = req.reply_to_msg_id
            
    mock_msg = MockMessage()
    
    # Mock Client
    class MockClient:
        async def get_messages(self, *args, **kwargs):
            return []
        async def send_message(self, *args, **kwargs):
            pass
        async def send_file(self, *args, **kwargs):
            pass
            
    mock_client = MockClient()

    # Construct Context
    ctx = MessageContext(
        client=mock_client,
        task_id=0,
        chat_id=req.chat_id,
        message_id=mock_msg.id,
        message_obj=mock_msg,
        is_sim=True
    )
    
    # Get Pipeline
    pipeline = None
    if container.worker and container.worker.pipeline:
        pipeline = container.worker.pipeline
    else:
        # Fallback construction (for dev/testing without worker)
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(container.rule_repo))
        pipeline.add(DedupMiddleware())
        pipeline.add(FilterMiddleware())
        try:
            from middlewares.ai import AIMiddleware
            pipeline.add(AIMiddleware())
        except ImportError:
            pass
        pipeline.add(SenderMiddleware(container.bus))

    # Execute
    try:
        await pipeline.execute(ctx)
    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        ctx.log_trace("Pipeline", "ERROR", {"error": str(e)})

    return {"trace": ctx.trace}
