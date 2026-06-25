import copy
import json as json

from libs.picoharness import harness
from libs.picoharness.struct.LMDriver import LMDriver


class TokenUsage:
    """Accumulates token counts reported by drivers that support usage data."""

    def __init__(self) -> None:
        self._inputs: int = 0
        self._outputs: int = 0
        self._reasoning: int = 0

    def add(self, usage: dict | None) -> None:
        if not usage:
            return

        # Drivers normalize provider-specific usage fields to these keys.
        self._inputs += self._safe_int(usage.get("input", 0))
        self._outputs += self._safe_int(usage.get("output", 0))
        self._reasoning += self._safe_int(usage.get("reasoning", 0))

    def inputs(self) -> int:
        return self._inputs

    def outputs(self) -> int:
        return self._outputs

    def reasoning(self) -> int:
        return self._reasoning

    def output_only(self) -> int:
        # Most APIs include reasoning tokens inside completion/output tokens.
        return max(0, self._outputs - self._reasoning)

    def all(self) -> int:
        return self._inputs + self._outputs

    def reset(self) -> None:
        self._inputs = 0
        self._outputs = 0
        self._reasoning = 0

    def snapshot(self) -> dict:
        return {
            "inputs": self.inputs(),
            "outputs": self.outputs(),
            "reasoning": self.reasoning(),
            "output_only": self.output_only(),
            "all": self.all(),
        }

    def _safe_int(self, value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


class LanguageModel:

    def __init__(self):
        self.histories    : list[dict]    = []
        self.model_config : dict          = {}
        self.driver_config: dict          = {}
        self.driver       : LMDriver|None = None
        self._token_usage : TokenUsage    = TokenUsage()

        self.rolename_user     : str = "user"
        self.rolename_assistant: str = "assistant"
        self.rolename_tool     : str = "tool"

        # Model configuration - System prompt
        self.cfg_model_system_prompt: str | None = ""

        # Harness configuration - Tool calling
        self.cfg_harness_max_tool_calling_chains: int = 100

        # Harness configuration - Thinking handler
        self.cfg_merge_reasoning_in_response: bool = False
        self.cfg_harness_reasoning_supported: bool = False
        self.cfg_harness_reasoning_start    : str  = "<think>"
        self.cfg_harness_reasoning_end      : str  = "</think>"

        # Harness configuration - Compacting trigger
        self.cfg_harness_context_compacting_enable: bool = False
        self.cfg_harness_context_compacting_length: int  = 20480


    def using(self, driver: LMDriver) -> "LanguageModel":
        self.driver = driver
        return self

    def add_history(self, role: str, content: str, extended_content: dict|None = None) -> "LanguageModel":

        # Base required objects
        base_object: dict = {
            "role": role,
            "content": content
        }

        # Additional objects to be merged into the base object if provided
        if extended_content is not None:
            base_object.update(extended_content)

        # Add to history
        self.histories.append(base_object)
        return self

    def remap_roles(self, role_mapping: dict[str, str]) -> "LanguageModel":
        for history in self.histories:
            if history["role"] in role_mapping:
                history["role"] = role_mapping[history["role"]]
        return self

    def history(self) -> list[dict]:
        # Enforce system prompt at the beginning of history
        if self.cfg_model_system_prompt:
            if not self.histories or self.histories[0]["role"] != "system":
                self.histories.insert(0, {"role": "system", "content": self.cfg_model_system_prompt})
        elif self.cfg_model_system_prompt is None:
            if self.histories and self.histories[0]["role"] == "system":
                self.histories.pop(0)
        return self.histories

    def clear(self) -> "LanguageModel":
        self.histories.clear()
        self._token_usage.reset()
        return self

    def chat(self, content: str, use_tools: bool = False) -> "LanguageModel":

        if use_tools:
            return self.chat_with_tool(content)

        self._assert_driver_initialized()
        self.add_history(self.rolename_user, content)

        # Send request to the driver
        result: dict = self.driver.send_request(self.history(), self.model_config, self.driver_config)
        self._record_token_usage(result)

        result_text: str = self._construct_response_text(result)
        self.add_history(self.rolename_assistant, result_text)

        return self

    def chat_with_tool(self, content: str) -> "LanguageModel":
        self._assert_driver_initialized()
        self.add_history(self.rolename_user, content)

        # Iterate loop until the model stops calling tools
        for i in range(0, self.cfg_harness_max_tool_calling_chains):

            # Get tools and request to model with tools
            tools: dict = harness.get_tools()
            result: dict = self.driver.send_request(self.history(), self.model_config, self.driver_config, tools=tools)
            self._record_token_usage(result)

            response_text: str = self._construct_response_text(result)

            # If tool is not found, then it is not a tool call
            # It is final response - exit tool call loop
            if "tool" not in result.keys():
                self.add_history(self.rolename_assistant, response_text)
                break

            # Get tool call string from response
            tool: str = result.get("tool", "{}")

            # Perform parsing
            # 파싱 실패시 다시 시도
            try:
                tool_call: dict = json.loads(tool)
            except json.decoder.JSONDecodeError:
                if self.driver.DEBUG_MODE:
                    print(f"    [DEBUG] Tool call failed due to broken json structure.")
                    print(f"    {tool}")
                    print(f"    [DEBUG] Retrying for tool call.")
                continue

            # Try executing tool
            # 실행 실패시 실패 사유를 맥락에 넣음
            try:
                tool_result: str = harness.execute(tool_call)
                self.add_history(self.rolename_assistant,response_text)
                self.add_history(self.rolename_tool, tool_result)
            except Exception as e:
                if self.driver.DEBUG_MODE:
                    print(f"    [DEBUG] Tool call failed while executing.")
                    print(f"    {e}")
                    print(f"    [DEBUG] Retrying for tool call.")

                self.add_history(self.rolename_tool, f"Tool execution error: {e}")

            continue

        return self

    def json(self, content: str, structure: dict) -> tuple["LanguageModel", dict|list|None]:
        self._assert_driver_initialized()
        self.add_history(self.rolename_user, content)

        # Send request to the driver
        result: dict|list|None = self.driver.send_request_ensure_structured(self.history(), structure, self.model_config)
        self._token_usage.add(self.driver.last_usage)

        if result is None:
            raise ValueError("Driver returned None for structured response. Please check the driver implementation.")

        self.add_history(self.rolename_assistant, str(result))

        return self, result

    def tool_result(self, content: str) -> "LanguageModel":
        return self.add_history(self.rolename_tool, content)

    def snapshot(self) -> "LanguageModel":
        return copy.deepcopy(self)

    def construct(self) -> list[dict]:
        return self.history()

    def token_usage(self) -> TokenUsage:
        return self._token_usage

    def response(self) -> str:
        if not self.history():
            return ""
        last_entry = self.histories[-1]
        if last_entry["role"] == self.rolename_assistant:
            return last_entry["content"]
        return ""

    ########################
    #                      #
    #  INTERNAL FUNCTIONS  #
    #                      #
    ########################

    def _assert_driver_initialized(self):
        if self.driver is None:
            raise ValueError("Driver is not initialized. Please call 'using(driver)' before using the LanguageModel.")

    def _record_token_usage(self, result: dict) -> None:
        self._token_usage.add(result.get("usage"))

    def _construct_response_text(self, result: dict) -> str:
        result_text: str = ""

        # Merge reasoning CoT to response history if configured
        if self.cfg_merge_reasoning_in_response and self.cfg_harness_reasoning_supported:
            result_text = self.cfg_harness_reasoning_start
            result_text += result.get("reasoning", "")
            result_text += self.cfg_harness_reasoning_end

        # Add response to history
        result_text += result.get("response", "")
        return result_text
