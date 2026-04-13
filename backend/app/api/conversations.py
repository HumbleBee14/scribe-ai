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


# ---------------------------------------------------------------------------
# Memories (per-product preferences)
# ---------------------------------------------------------------------------

class AddMemoryRequest(BaseModel):
    content: str


@router.get("/api/products/{product_id}/memories")
def list_memories_api(product_id: str) -> dict:
    return {"memories": db.get_memories(product_id), "max": db.MAX_MEMORIES_PER_PRODUCT}


@router.post("/api/products/{product_id}/memories")
def add_memory_api(product_id: str, req: AddMemoryRequest) -> dict:
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    result = db.add_memory(product_id, req.content.strip(), source="user")
    if result is None:
        raise HTTPException(status_code=400, detail=f"Maximum {db.MAX_MEMORIES_PER_PRODUCT} memories reached")
    return result


@router.delete("/api/memories/{memory_id}")
def delete_memory_api(memory_id: int) -> dict:
    if not db.delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": True}
