from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from models.models import get_async_session, RSSSubscription
from web_admin.rss.models.schemas import RSSSubscriptionCreate, RSSSubscriptionUpdate, RSSSubscriptionResponse
from core.container import container
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscriptions", tags=["rss_subscriptions"])

@router.get("/", response_model=List[RSSSubscriptionResponse])
async def list_subscriptions(
    skip: int = 0, 
    limit: int = 100, 
    session: AsyncSession = Depends(get_async_session)
):
    stmt = select(RSSSubscription).offset(skip).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()

@router.post("/", response_model=RSSSubscriptionResponse)
async def create_subscription(
    sub_in: RSSSubscriptionCreate, 
    session: AsyncSession = Depends(get_async_session)
):
    sub = RSSSubscription(**sub_in.dict())
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    
    # Notify RSSPullService
    if container.rss_puller:
        container.rss_puller.add_new_subscription(sub.id)
    
    return sub

@router.put("/{sub_id}", response_model=RSSSubscriptionResponse)
async def update_subscription(
    sub_id: int, 
    sub_in: RSSSubscriptionUpdate, 
    session: AsyncSession = Depends(get_async_session)
):
    sub = await session.get(RSSSubscription, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    update_data = sub_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(sub, key, value)
    
    # Reset AIMD if interval config changed drastically? 
    # For now, just let AIMD adjust itself.
    
    await session.commit()
    await session.refresh(sub)
    return sub

@router.delete("/{sub_id}")
async def delete_subscription(
    sub_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    sub = await session.get(RSSSubscription, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    await session.delete(sub)
    await session.commit()
    
    # We should probably notify RSSPullService to stop, but HashedTimingWheel 
    # doesn't support easy task removal by key yet (it supports by task_id but we need access to it).
    # RSSPullService will find out on next execution that sub is gone or inactive.
    
    return {"success": True}

@router.post("/{sub_id}/refresh")
async def refresh_subscription(
    sub_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    sub = await session.get(RSSSubscription, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    if container.rss_puller:
        # Trigger immediate pull in background
        # We can re-schedule it with 0 delay or call pull_task directly
        # But properly we should use add_task with 0 delay.
        # But rss_puller.timing_wheel.add_task is sync or async?
        # It's sync method adding to wheel.
        # We need to find the task_id. task_id = f"rss_pull_{sub.id}"
        
        # Directly calling pull_task might be easier if safe.
        # Let's verify RSSPullService.pull_task is async. Yes.
        # We can just run it.
        import asyncio
        asyncio.create_task(container.rss_puller.pull_task(sub_id))
        
        return {"success": True, "message": "Refresh triggered"}
    
    return {"success": False, "message": "RSS Pull Service not running"}
