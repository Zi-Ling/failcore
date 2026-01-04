# failcore/web/routes/api/events_api.py
"""
Events API - placeholder for real-time event streaming

Provides SSE endpoint for streaming cost-related events (blocked steps, etc.).
Currently a placeholder that will be implemented in future iterations.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional
import json
import asyncio

from failcore.web.services.events_service import get_events_service

router = APIRouter(prefix="/api/runs")


@router.get("/{run_id}/events")
async def stream_run_events(
    run_id: str,
    last_seq: Optional[int] = None,
):
    """
    Stream events for a run (SSE endpoint - placeholder)
    
    Args:
        run_id: Run ID
        last_seq: Last event sequence number (for resume)
    
    Returns:
        SSE stream of events
    
    Event format:
    {
        "type": "blocked" | "budget_exceeded" | "burn_rate_exceeded",
        "seq": int,
        "ts": str (ISO timestamp),
        "reason": str,
        "error_code": Optional[str]
    }
    
    TODO: Replace with actual SSE implementation
    """
    events_service = get_events_service()
    
    async def event_generator():
        """
        SSE event generator
        
        Streams events from trace file for the run.
        """
        try:
            # Send initial connection message
            yield "data: {}\n\n".format(json.dumps({
                "type": "connected",
                "run_id": run_id,
            }))
            
            # Stream events from trace
            async for event in events_service.stream_run_events(run_id, last_seq):
                yield "data: {}\n\n".format(json.dumps(event))
            
            # Send end message
            yield "data: {}\n\n".format(json.dumps({
                "type": "end",
                "message": "Stream completed",
            }))
        except Exception as e:
            yield "data: {}\n\n".format(json.dumps({
                "type": "error",
                "error": str(e),
            }))
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/{run_id}/events/list")
async def get_run_events(
    run_id: str,
    event_type: Optional[str] = None,
    limit: Optional[int] = None,
):
    """
    Get events for a run (non-streaming, placeholder)
    
    Args:
        run_id: Run ID
        event_type: Optional event type filter
        limit: Optional limit on number of events
    
    Returns:
        List of events
    
    TODO: Replace with actual implementation
    """
    events_service = get_events_service()
    
    try:
        events = events_service.get_run_events(run_id, event_type, limit)
        return {
            "run_id": run_id,
            "events": events,
            "count": len(events),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
