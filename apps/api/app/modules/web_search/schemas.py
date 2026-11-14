from datetime import date
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.command.schemas import MAX_COMMAND_CHARS, CommandContext
from app.modules.web_search.services import (
    DEFAULT_MAX_RESULTS,
    MAX_MAX_RESULTS,
    MIN_MAX_RESULTS,
)


class SearchRequest(BaseModel):
    """Validated payload for the web search endpoint."""

    query: str | None = None
    text: str | None = Field(default=None, min_length=1, max_length=MAX_COMMAND_CHARS)
    timezone: str | None = None
    context: CommandContext | None = None
    max_results: int = DEFAULT_MAX_RESULTS
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def _require_one_search_input(self) -> Self:
        if (self.query is None) == (self.text is None):
            raise ValueError("Provide either query or command text.")
        if self.text is not None and (self.date_from is not None or self.date_to is not None):
            raise ValueError("Provide date filters with a query or let the parser extract them.")
        if self.date_from is not None and self.date_to is not None and self.date_from > self.date_to:
            raise ValueError("date_from must be on or before date_to.")
        return self

    @field_validator("query")
    @classmethod
    def _query_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("A non-empty search query is required.")
        return cleaned

    @field_validator("max_results")
    @classmethod
    def _max_results_within_range(cls, value: int) -> int:
        if not MIN_MAX_RESULTS <= value <= MAX_MAX_RESULTS:
            raise ValueError(
                f"max_results must be between {MIN_MAX_RESULTS} and {MAX_MAX_RESULTS}."
            )
        return value


class SearchResult(BaseModel):
    """A single normalized search result."""

    title: str
    url: str
    snippet: str


class SearchData(BaseModel):
    """Payload returned by a successful web search."""

    query: str
    results: list[SearchResult]


class ErrorDetail(BaseModel):
    """Machine-readable error information."""

    code: str
    message: str


class SearchResponse(BaseModel):
    """Standardized response envelope used by the search API."""

    success: bool
    data: SearchData | None = None
    error: ErrorDetail | None = None
