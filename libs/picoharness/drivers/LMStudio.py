import json
import time
from urllib import error, request
from urllib.parse import urlparse

from libs.picoharness.struct.LMDriver import LMDriver


class LMStudio(LMDriver):

    def __init__(self, context: int, url: str, model: str, model_config: dict) -> None:
        super().__init__("LMStudio", context, url, model, model_config)

    def tokenizer(self, histories: list[dict]) -> int:
        # LM Studio does not expose a tokenizer here; this is a rough estimate.
        text = "\n".join(str(history.get("content", "")) for history in histories)
        return max(1, len(text) // 4)

    def send_request(self, histories: list[dict], model_config: dict|None = None, structure: dict | None = None, tools: dict | None = None, max_retries: int = 3, delay_until_next_retry: float = 3.0) -> dict:
        payload = self._build_payload(histories, model_config, structure, tools)
        endpoint = self._endpoint()
        last_error: Exception | None = None

        for trial in range(max_retries):
            try:
                if self.DEBUG_MODE:
                    print(f"    [DEBUG] Sending request to {endpoint}")

                data = self._post_json(endpoint, payload)

                if self.DEBUG_MODE:
                    print(f"    [DEBUG] Response from model: {data}")

                return self._parse_response(data, tools)
            except Exception as error:
                last_error = error
                if self.DEBUG_MODE:
                    print(f"    [DEBUG] LMStudio request failed ({trial + 1}/{max_retries}): {error}")
                if trial < max_retries - 1:
                    time.sleep(delay_until_next_retry)

        raise RuntimeError(f"LMStudio request failed after {max_retries} retries: {last_error}")

    def _post_json(self, endpoint: str, payload: dict) -> dict:
        # Use the standard library so the driver can be imported before uv sync.
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as http_error:
            detail = http_error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {http_error.code}: {detail}") from http_error

    def _endpoint(self) -> str:
        raw_url = self.url.strip()
        if not raw_url:
            raw_url = "localhost"
        if "://" not in raw_url:
            raw_url = f"http://{raw_url}"

        # A bare host/IP should target LM Studio's default API port.
        parsed = urlparse(raw_url)
        netloc = parsed.netloc
        if ":" not in netloc:
            netloc = f"{netloc}:1234"

        base_url = parsed._replace(netloc=netloc, path="", params="", query="", fragment="").geturl()
        return f"{base_url.rstrip('/')}/v1/chat/completions"

    def _build_payload(self, histories: list[dict], model_config: dict | None, structure: dict | None, tools: dict | None) -> dict:
        payload: dict = {
            "messages": self._normalize_histories(histories),
            **self.default_model_config,
            **(model_config or {}),
        }

        if self.model:
            payload["model"] = self.model

        if structure:
            # LM Studio follows the OpenAI-compatible structured output shape.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": structure,
            }

        tool_list = self._normalize_tools(tools)
        if tool_list:
            payload["tools"] = tool_list
            payload["tool_choice"] = "auto"

        return payload

    def _normalize_histories(self, histories: list[dict]) -> list[dict]:
        messages: list[dict] = []

        for history in histories:
            role = history.get("role", "user")
            content = history.get("content", "")

            if role == "tool":
                # Some local servers do not accept tool-role messages reliably.
                messages.append({
                    "role": "user",
                    "content": f"Tool result:\n{content}",
                })
                continue

            if role not in {"system", "user", "assistant"}:
                role = "user"

            messages.append({
                "role": role,
                "content": content,
            })

        return messages

    def _normalize_tools(self, tools: dict | None) -> list[dict]:
        if not tools:
            return []

        if isinstance(tools, dict) and isinstance(tools.get("tools"), list):
            return tools["tools"]

        if isinstance(tools, list):
            return tools

        return []

    def _parse_response(self, data: dict, tools: dict | None) -> dict:
        choices = data.get("choices", [])
        if not choices:
            return {
                "response": "",
                "usage": self._parse_usage(data),
            }

        message = choices[0].get("message", {})
        content = message.get("content") or ""
        result: dict = {
            "response": content,
            "usage": self._parse_usage(data),
        }

        reasoning = message.get("reasoning") or message.get("reasoning_content")
        if reasoning:
            result["reasoning"] = reasoning

        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            # Prefer native OpenAI-style tool calls when the server returns them.
            function = tool_calls[0].get("function", {})
            arguments = function.get("arguments") or "{}"
            try:
                parameters = json.loads(arguments) if isinstance(arguments, str) else arguments
            except json.decoder.JSONDecodeError:
                parameters = arguments

            result["tool"] = json.dumps({
                "name": function.get("name", ""),
                "parameters": parameters,
            }, ensure_ascii=False)
            return result

        if tools:
            # Fallback for local models that emit the tool call as JSON text.
            parsed_tool = self._parse_text_tool_call(content)
            if parsed_tool is not None:
                result["tool"] = json.dumps(parsed_tool, ensure_ascii=False)

        return result

    def _parse_usage(self, data: dict) -> dict:
        usage = data.get("usage") or {}
        completion_details = usage.get("completion_tokens_details") or {}

        reasoning_tokens = (
            completion_details.get("reasoning_tokens")
            or usage.get("reasoning_tokens")
            or 0
        )

        return {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
            "reasoning": reasoning_tokens,
        }

    def _parse_text_tool_call(self, content: str) -> dict | None:
        try:
            parsed = json.loads(content)
        except json.decoder.JSONDecodeError:
            return None

        if not isinstance(parsed, dict):
            return None

        name = parsed.get("name") or parsed.get("tool") or parsed.get("tool_name")
        parameters = parsed.get("parameters") or parsed.get("arguments") or {}

        if isinstance(name, str) and name:
            return {
                "name": name,
                "parameters": parameters,
            }

        return None
