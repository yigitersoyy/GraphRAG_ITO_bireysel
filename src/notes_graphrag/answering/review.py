"""Model-assisted relevance/support review; not an independent correctness guarantee."""

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REVIEW_SYSTEM = (Path(__file__).parent.parent / "prompts" / "review_v1.txt").read_text("utf-8")
ANSWERABILITY_SYSTEM = (
    Path(__file__).parent.parent / "prompts" / "answerability_v1.txt"
).read_text("utf-8")


class Answerability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answerable: bool
    reason: str = Field(min_length=1, max_length=300)


InformationKind = Literal[
    "OTHER",
    "PROGRAMMING_LANGUAGE",
    "DATABASE",
    "PERSON",
    "PROJECT",
    "ORGANIZATION",
    "PLACE",
    "TIME",
    "AMOUNT",
    "CONTACT_DETAIL",
    "EVENT",
]


def explicit_requested_kind(question: str) -> InformationKind | None:
    """Honor an explicitly requested type instead of letting a model relabel the question.

    A narrow bilingual intent rule, not a fact lookup or an answer dictionary. Other
    phrasings/categories remain model-assisted and can still be misclassified.
    """
    if re.search(
        r"\b(?:which|what)\s+programming\s+languages?\b|\bhangi\s+programlama\s+dil\w*",
        question,
        re.IGNORECASE,
    ):
        return "PROGRAMMING_LANGUAGE"
    return None


class AnswerReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Constrained runtimes emit property order. Ground the decision before committing
    # to a category; choosing the category first caused correct answers to be rejected.
    reason: str = Field(min_length=1, max_length=300)
    requested_kind: InformationKind
    candidate_kind: InformationKind
    supported: bool
