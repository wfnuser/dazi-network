from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal


# --- Profile ---

class BasicInfo(BaseModel):
    birth_year: int = Field(..., ge=1920, le=2010)
    gender: Literal["M", "F", "O"]
    city: str = Field(..., min_length=1, max_length=50)


class ContactInfo(BaseModel):
    type: Literal["wechat", "telegram", "twitter", "jike", "email"]
    value: str = Field(..., min_length=1, max_length=100)


class ProfileRequest(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=20)
    basic: BasicInfo
    tags: list[str] = Field(..., min_length=3, max_length=3)
    contact: ContactInfo

    def model_post_init(self, __context):
        for i, tag in enumerate(self.tags):
            if len(tag) < 1 or len(tag) > 200:
                raise ValueError(f"Tag {i+1} must be 1-200 chars, got {len(tag)}")


class ProfileResponse(BaseModel):
    did: str
    nickname: str
    version: int
    created_at: str


# --- Search ---

class SearchRequest(BaseModel):
    intent: str = Field(..., min_length=1, max_length=500)


class CandidateResult(BaseModel):
    nickname: str
    tags: list[str]


class SearchResponse(BaseModel):
    candidates: list[CandidateResult]
    total: int


# --- Interest ---

class InterestRequest(BaseModel):
    target_nickname: str = Field(..., min_length=1)


class InterestResponse(BaseModel):
    status: Literal["pending", "matched"]
    contact: ContactInfo | None = None
    message: str


# --- Connections ---

class PendingConnection(BaseModel):
    nickname: str
    tags: list[str]


class MatchedConnection(BaseModel):
    nickname: str
    tags: list[str]
    contact: ContactInfo
    matched_at: str


class ConnectionsResponse(BaseModel):
    pending_incoming: list[PendingConnection]
    pending_outgoing: list[PendingConnection]
    matched: list[MatchedConnection]


# --- Errors ---

class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict | None = None


class DeleteResponse(BaseModel):
    message: str
