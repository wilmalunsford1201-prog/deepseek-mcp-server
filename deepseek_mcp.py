#!/usr/bin/env python3
"""
DeepSeek MCP Server — Connect any MCP client (Claude, Cursor, ...) to the DeepSeek API.

Provides tools for text generation, multi-turn chat, transparent reasoning
(DeepSeek-R1 with visible chain-of-thought), and model listing.

Usage:
    export DEEPSEEK_API_KEY="your-api-key"
    python deepseek_mcp.py

Get a key at https://platform.deepseek.com/api_keys
"""

import json
import os
from typing import Optional, List, Dict, Any
from enum import Enum

import httpx
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# ── Server Init ──────────────────────────────────────────────────────────────
mcp = FastMCP("deepseek_mcp")

# ── Constants ────────────────────────────────────────────────────────────────
API_BASE_URL = "https://api.deepseek.com"       # OpenAI-compatible endpoint
CHAT_MODEL = "deepseek-chat"                     # DeepSeek-V3
REASONER_MODEL = "deepseek-reasoner"             # DeepSeek-R1 (returns reasoning_content)
TIMEOUT = 180.0

AVAILABLE_MODELS = ["deepseek-chat", "deepseek-reasoner"]


# ── Enums ────────────────────────────────────────────────────────────────────
class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"

class ChatRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


# ── Shared Utilities ─────────────────────────────────────────────────────────
def _get_api_key() -> str:
    """Retrieve API key from environment."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise ValueError(
            "No API key found. Set the DEEPSEEK_API_KEY environment variable. "
            "Get a key at https://platform.deepseek.com/api_keys"
        )
    return key


async def _post_chat(body: dict) -> dict:
    """Reusable async client for the OpenAI-compatible /chat/completions endpoint."""
    api_key = _get_api_key()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_BASE_URL}/chat/completions",
            headers=headers,
            json=body,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()


async def _get(endpoint: str) -> dict:
    api_key = _get_api_key()
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE_URL}/{endpoint}", headers=headers, timeout=30.0)
        resp.raise_for_status()
        return resp.json()


def _handle_error(e: Exception) -> str:
    """Consistent error formatting."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        try:
            detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            detail = e.response.text[:300]
        error_map = {
            400: f"Bad request: {detail}. Check your parameters.",
            401: "Invalid API key. Get one at https://platform.deepseek.com/api_keys",
            402: "Insufficient balance. Top up at https://platform.deepseek.com.",
            422: f"Invalid parameters: {detail}",
            429: "Rate limit reached. Wait a moment and retry.",
            500: "DeepSeek server error. Try again shortly.",
            503: "Server overloaded. Try again shortly.",
        }
        return f"Error: {error_map.get(status, f'HTTP {status}: {detail}')}"
    if isinstance(e, httpx.TimeoutException):
        return f"Error: Request timed out ({int(TIMEOUT)}s). Try a shorter input."
    if isinstance(e, ValueError):
        return f"Error: {e}"
    return f"Error: {type(e).__name__}: {e}"


def _usage_line(data: dict, model: str) -> str:
    u = data.get("usage", {})
    if not u:
        return ""
    return (f"\n\n---\n_Tokens: {u.get('prompt_tokens', '?')} in → "
            f"{u.get('completion_tokens', '?')} out | Model: {model}_")


# ── Pydantic Input Models ────────────────────────────────────────────────────
class GenerateInput(BaseModel):
    """Input for single-turn text generation."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    prompt: str = Field(..., description="The text prompt to send to DeepSeek", min_length=1, max_length=200000)
    system_instruction: Optional[str] = Field(default=None, description="System instruction to guide behavior")
    temperature: Optional[float] = Field(default=None, description="Creativity (0.0=deterministic, 2.0=creative)", ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, description="Maximum output tokens", ge=1, le=8192)
    json_mode: bool = Field(default=False, description="Force DeepSeek to output valid JSON")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output: markdown or raw json")


class ChatMessage(BaseModel):
    role: ChatRole = Field(..., description="Message role: system | user | assistant")
    content: str = Field(..., description="Message content", min_length=1)


class ChatInput(BaseModel):
    """Input for multi-turn chat."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    messages: List[ChatMessage] = Field(..., description="Chat history as list of {role, content}", min_length=1)
    model: str = Field(default=CHAT_MODEL, description=f"Model name ({' | '.join(AVAILABLE_MODELS)})")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=8192)


class ReasonInput(BaseModel):
    """Input for DeepSeek-R1 reasoning with visible chain-of-thought."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    prompt: str = Field(..., description="A hard problem for the reasoning model to think through", min_length=1)
    show_reasoning: bool = Field(default=True, description="Include the model's reasoning trace in the output")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=8192)


class ListModelsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


# ── Tool Implementations ─────────────────────────────────────────────────────
@mcp.tool(
    name="deepseek_generate",
    annotations={"title": "Generate Text with DeepSeek", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def deepseek_generate(params: GenerateInput) -> str:
    """Generate text with DeepSeek-V3 (deepseek-chat). Single-turn: writing, code, analysis,
    translation, summarization, Q&A. Supports system instructions, temperature, and JSON mode.
    """
    try:
        messages = []
        if params.system_instruction:
            messages.append({"role": "system", "content": params.system_instruction})
        messages.append({"role": "user", "content": params.prompt})

        body: Dict[str, Any] = {"model": CHAT_MODEL, "messages": messages, "stream": False}
        if params.temperature is not None:
            body["temperature"] = params.temperature
        if params.max_tokens is not None:
            body["max_tokens"] = params.max_tokens
        if params.json_mode:
            body["response_format"] = {"type": "json_object"}

        data = await _post_chat(body)
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(data, indent=2, ensure_ascii=False)
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "[Empty response]")
        return text + _usage_line(data, CHAT_MODEL)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="deepseek_chat",
    annotations={"title": "Multi-turn Chat with DeepSeek", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def deepseek_chat(params: ChatInput) -> str:
    """Multi-turn conversation with DeepSeek. Send full history, get the next reply.
    Set model=deepseek-reasoner for step-by-step reasoning, deepseek-chat for general use.
    """
    try:
        body: Dict[str, Any] = {
            "model": params.model,
            "messages": [{"role": m.role.value, "content": m.content} for m in params.messages],
            "stream": False,
        }
        if params.temperature is not None:
            body["temperature"] = params.temperature
        if params.max_tokens is not None:
            body["max_tokens"] = params.max_tokens

        data = await _post_chat(body)
        msg = data.get("choices", [{}])[0].get("message", {})
        out = msg.get("content", "[Empty response]")
        reasoning = msg.get("reasoning_content")
        if reasoning:
            out = f"<thinking>\n{reasoning}\n</thinking>\n\n{out}"
        return out + _usage_line(data, params.model)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="deepseek_reason",
    annotations={"title": "Deep Reasoning with DeepSeek-R1", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def deepseek_reason(params: ReasonInput) -> str:
    """Solve a hard problem with DeepSeek-R1 (deepseek-reasoner). Best for math, logic,
    multi-step analysis, and code debugging. Optionally returns the visible reasoning trace.
    """
    try:
        body: Dict[str, Any] = {
            "model": REASONER_MODEL,
            "messages": [{"role": "user", "content": params.prompt}],
            "stream": False,
        }
        if params.max_tokens is not None:
            body["max_tokens"] = params.max_tokens

        data = await _post_chat(body)
        msg = data.get("choices", [{}])[0].get("message", {})
        answer = msg.get("content", "[Empty response]")
        reasoning = msg.get("reasoning_content", "")
        if params.show_reasoning and reasoning:
            return f"## Reasoning\n{reasoning}\n\n## Answer\n{answer}" + _usage_line(data, REASONER_MODEL)
        return answer + _usage_line(data, REASONER_MODEL)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="deepseek_list_models",
    annotations={"title": "List DeepSeek Models", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def deepseek_list_models(params: ListModelsInput) -> str:
    """List models available to your DeepSeek API key."""
    try:
        data = await _get("models")
        models = data.get("data", [])
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(models, indent=2, ensure_ascii=False)
        lines = ["# Available DeepSeek Models\n"]
        for m in models:
            lines.append(f"- `{m.get('id', '?')}`  (owned by {m.get('owned_by', 'deepseek')})")
        lines.append(f"\n_Total: {len(models)} models_")
        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()
