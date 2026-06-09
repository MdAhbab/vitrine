from __future__ import annotations

from pydantic import BaseModel

# Mirrors frontend `Thread` / `Message` (store.ts). NOTE the frontend calls a
# chat a "thread" and uses `threadId`; the backend table is `chats` with `id`.
# The serializer maps chat.id -> threadId.


class MessageOut(BaseModel):
    id: str
    threadId: str
    authorId: str
    authorName: str
    isAgent: bool | None = None
    body: str
    ts: int  # epoch ms


class ThreadOut(BaseModel):
    id: str
    productId: str
    productName: str
    productCover: str
    buyerId: str
    buyerName: str
    sellerId: str
    sellerName: str
    isAgent: bool
    agentBudget: float | None = None
    status: str  # open | closed | settled
    unreadFor: list[str]
    createdAt: int  # epoch ms


class SendMessageIn(BaseModel):
    body: str
    as_agent: bool = False


class StartNegotiationIn(BaseModel):
    listing_id: str
    budget: float                 # max the buyer authorizes the rep to spend
    readme_context: str = ""      # buyer brief the rep references
