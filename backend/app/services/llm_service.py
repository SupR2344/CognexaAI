"""Ollama LLM Service for Cognexa AI.

Provides asynchronous access to Ollama chat, streaming, and tool calling endpoints
with retry logic, timeout handling, and configuration integration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx

logger = logging.getLogger(__name__)

# Fallback config resolution
try:
    from app.config import settings  # type: ignore

    DEFAULT_BASE_URL = getattr(
        settings, "OLLAMA_BASE_URL", getattr(settings, "ollama_base_url", "http://localhost:11434")
    )
    DEFAULT_MODEL = getattr(
        settings, "OLLAMA_MODEL", getattr(settings, "ollama_model", "qwen2.5:7b")
    )
except Exception:
    DEFAULT_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


class OllamaServiceError(Exception):
    """Base exception for Ollama service errors."""
    pass


class OllamaLLMService:
    """Service interfacing with Ollama for text generation, streaming, and tool invocation."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize Ollama LLM Service.

        Args:
            base_url: Ollama API base URL (defaults to config / OLLAMA_BASE_URL).
            model: Model name to use (defaults to config / OLLAMA_MODEL).
            timeout: HTTP request timeout in seconds.
            max_retries: Number of retry attempts on transient network errors.
            retry_delay: Initial retry backoff delay in seconds.
        """
        raw_url = base_url or DEFAULT_BASE_URL or "http://localhost:11434"
        self.base_url = raw_url.rstrip("/")
        self.model = model or DEFAULT_MODEL or "qwen2.5:7b"
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _format_messages(
        self, system_prompt: Optional[str], prompt: str
    ) -> List[Dict[str, str]]:
        """Format prompt and optional system prompt for Ollama's chat API.

        Args:
            system_prompt: Optional system prompt to instruct the model.
            prompt: User prompt content.

        Returns:
            List of message dictionaries with 'role' and 'content'.
        """
        messages: List[Dict[str, str]] = []
        if system_prompt and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _format_tool_definition(self, tool: Any) -> Dict[str, Any]:
        """Convert a LangChain tool or dictionary schema to Ollama/OpenAI tool format.

        Args:
            tool: LangChain BaseTool, dictionary schema, or callable tool.

        Returns:
            Dictionary matching the OpenAI/Ollama function calling schema.
        """
        # If already formatted as OpenAI/Ollama tool
        if isinstance(tool, dict) and "type" in tool and "function" in tool:
            return tool

        # If it's a raw function dict
        if isinstance(tool, dict):
            name = tool.get("name", "unnamed_tool")
            description = tool.get("description", "")
            parameters = tool.get("parameters", {"type": "object", "properties": {}})
            return {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            }

        # If it's a LangChain tool instance
        name = getattr(tool, "name", tool.__class__.__name__)
        description = getattr(tool, "description", "")
        parameters: Dict[str, Any] = {"type": "object", "properties": {}}

        if hasattr(tool, "args_schema") and tool.args_schema:
            try:
                # Pydantic v1 vs v2 schema extraction
                if hasattr(tool.args_schema, "model_json_schema"):
                    parameters = tool.args_schema.model_json_schema()
                elif hasattr(tool.args_schema, "schema"):
                    parameters = tool.args_schema.schema()
            except Exception as e:
                logger.warning("Could not extract schema for tool %s: %s", name, e)

        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }

    async def _execute_with_retry(self, client: httpx.AsyncClient, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Execute an HTTP request with exponential backoff retry.

        Args:
            client: httpx.AsyncClient instance.
            method: HTTP method.
            url: Request URL.
            **kwargs: Extra parameters passed to client.request.

        Returns:
            httpx.Response on success.

        Raises:
            OllamaServiceError: When retries are exhausted or server error occurs.
        """
        last_exception: Optional[Exception] = None
        current_delay = self.retry_delay

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as err:
                last_exception = err
                logger.warning(
                    "Ollama request failed (attempt %d/%d): %s. Retrying in %.1fs...",
                    attempt,
                    self.max_retries,
                    err,
                    current_delay,
                )
            except httpx.HTTPStatusError as err:
                last_exception = err
                if 500 <= err.response.status_code < 600:
                    logger.warning(
                        "Ollama 5xx server error (%d) on attempt %d/%d. Retrying in %.1fs...",
                        err.response.status_code,
                        attempt,
                        self.max_retries,
                        current_delay,
                    )
                else:
                    # Client errors (4xx) should fail immediately without retry
                    raise OllamaServiceError(
                        f"Ollama client error {err.response.status_code}: {err.response.text}"
                    ) from err

            if attempt < self.max_retries:
                await asyncio.sleep(current_delay)
                current_delay *= 2.0

        raise OllamaServiceError(
            f"Failed to communicate with Ollama at {self.base_url} after {self.max_retries} attempts."
        ) from last_exception

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate a complete text response from Ollama.

        Args:
            prompt: User prompt content.
            system_prompt: Optional system instructions.
            temperature: Sampling temperature (0.0 to 1.0).

        Returns:
            Completed generated text response string.

        Raises:
            OllamaServiceError: If communication fails.
        """
        messages = self._format_messages(system_prompt, prompt)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await self._execute_with_retry(
                    client,
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                data = response.json()
                message = data.get("message", {})
                return message.get("content", "")
            except Exception as err:
                logger.error("Error during Ollama generate: %s", err, exc_info=True)
                raise OllamaServiceError(f"Error during Ollama generate: {err}") from err

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from Ollama chat endpoint.

        Args:
            prompt: User prompt content.
            system_prompt: Optional system instructions.
            temperature: Sampling temperature.

        Yields:
            Token chunks as strings as they arrive.
        """
        messages = self._format_messages(system_prompt, prompt)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            message = chunk.get("message", {})
                            content = message.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            logger.debug("Failed to parse JSON streaming line: %s", line)
            except Exception as err:
                logger.error("Streaming error from Ollama: %s", err, exc_info=True)
                raise OllamaServiceError(f"Streaming error from Ollama: {err}") from err

    async def generate_with_tools(
        self,
        prompt: str,
        tools: List[Any],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate response with Ollama tool/function calling capability.

        Args:
            prompt: User prompt content.
            tools: List of tools (LangChain BaseTool objects or OpenAI tool schemas).
            system_prompt: Optional system instructions.

        Returns:
            Dictionary containing:
                - content: Text content returned by the model.
                - tool_calls: List of requested tool calls with function name and arguments.
        """
        messages = self._format_messages(system_prompt, prompt)
        formatted_tools = [self._format_tool_definition(t) for t in tools]

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": formatted_tools,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await self._execute_with_retry(
                    client,
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                data = response.json()
                message = data.get("message", {})
                content = message.get("content", "") or ""
                tool_calls = message.get("tool_calls", []) or []

                # Fallback: Parse embedded JSON tool call if model emitted JSON text
                if not tool_calls and "```json" in content:
                    try:
                        start = content.find("```json") + 7
                        end = content.find("```", start)
                        json_str = content[start:end].strip()
                        parsed = json.loads(json_str)
                        if isinstance(parsed, dict) and "name" in parsed and "arguments" in parsed:
                            tool_calls = [{"function": parsed}]
                        elif isinstance(parsed, list):
                            tool_calls = [{"function": item} for item in parsed if isinstance(item, dict) and "name" in item]
                    except Exception:
                        pass

                return {
                    "content": content,
                    "tool_calls": tool_calls,
                }
            except Exception as err:
                logger.error("Error during Ollama generate_with_tools: %s", err, exc_info=True)
                raise OllamaServiceError(f"Error during Ollama generate_with_tools: {err}") from err


# Singleton instance for dependency injection
_llm_service_instance: Optional[OllamaLLMService] = None


def get_llm_service(
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> OllamaLLMService:
    """Dependency provider for OllamaLLMService.

    Args:
        base_url: Optional custom base URL.
        model: Optional custom model name.

    Returns:
        Configured OllamaLLMService instance.
    """
    global _llm_service_instance
    if _llm_service_instance is None or base_url is not None or model is not None:
        _llm_service_instance = OllamaLLMService(base_url=base_url, model=model)
    return _llm_service_instance
