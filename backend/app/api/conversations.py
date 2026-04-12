"""Conversation CRUD API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import database as db

router = APIRouter(tags=["conversations"])


class UpdateConversationRequest(BaseModel):
    title: str


@router.get("/api/products/{product_id}/conversations")
def list_conversations_api(product_id: str) -> dict:
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")
    return {"conversations": db.list_conversations(product_id)}


@router.post("/api/products/{product_id}/conversations")
def create_conversation_api(product_id: str) -> dict:
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")
    return db.create_conversation(product_id)


@router.get("/api/conversations/{conversation_id}")
def get_conversation_api(conversation_id: str) -> dict:
    conv = db.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.patch("/api/conversations/{conversation_id}")
def update_conversation_api(conversation_id: str, req: UpdateConversationRequest) -> dict:
    conv = db.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.update_conversation_title(conversation_id, req.title.strip())
    return db.get_conversation(conversation_id)


@router.delete("/api/conversations/{conversation_id}")
def delete_conversation_api(conversation_id: str) -> dict:
    if not db.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True}
