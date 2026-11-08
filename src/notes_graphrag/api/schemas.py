from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NoteBody(BaseModel):
    title: str = Field(max_length=10_000)
    text: str = Field(max_length=2_000_000)
    format: Literal["plain_text", "markdown"] = "plain_text"
    auto_topic: bool = True


class QuestionBody(BaseModel):
    question: str = Field(max_length=10_000)
    include_graph: bool = False
