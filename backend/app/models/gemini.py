"""Pydantic schemas for Gemini AI service status, diagnostics, and structured outputs."""

from typing import Optional
from pydantic import BaseModel, Field


class GeminiStatusResponse(BaseModel):
  """Response schema for GET /api/v1/gemini/status."""

  configured: bool = Field(
      ..., description="Whether a valid non-placeholder Gemini API key is set"
  )
  model: str = Field(
      ..., description="The effective Gemini model name currently in use"
  )


class GeminiTokenUsage(BaseModel):
  """Token count metrics returned by the Gemini API."""

  prompt_tokens: Optional[int] = Field(
      default=None, description="Number of tokens in the input prompt"
  )
  candidates_tokens: Optional[int] = Field(
      default=None, description="Number of tokens in the generated response"
  )
  total_tokens: Optional[int] = Field(
      default=None, description="Total tokens processed in the transaction"
  )


class GeminiTestResponse(BaseModel):
  """Response schema for POST /api/v1/gemini/test diagnostic endpoint."""

  success: bool = Field(
      default=True, description="Whether the diagnostic call succeeded"
  )
  message: str = Field(
      ..., description="Generated text response from the Gemini model"
  )
  model: str = Field(..., description="The Gemini model that responded")
  latency_ms: float = Field(
      ..., description="Round-trip API latency in milliseconds"
  )
  token_usage: Optional[GeminiTokenUsage] = Field(
      default=None, description="Reported token usage breakdown"
  )
