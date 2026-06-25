import json
import time
from abc import abstractmethod, ABC

class LMDriver(ABC):
    def __init__(self, driver_name: str, context_window: int, url: str, model: str, default_model_config: dict) -> None:
        self.DEBUG_MODE: bool = False
        self.context_window: int = context_window
        self.driver_name: str = driver_name
        self.url: str = url
        self.model: str = model
        self.default_model_config: dict = default_model_config
        self.last_usage: dict | None = None

    @abstractmethod
    def send_request(self, histories: list[dict], model_config: dict|None = None, structure: dict|None = None, tools: dict|None = None, max_retries: int = 3, delay_until_next_retry: float = 3.0) -> dict:
        """
        Send a request to the language model driver.

        :param histories: The conversation history.
        :param model_config: Configuration for the language model inference such as temperature, top_p/k samplings, etc.
        :param structure: JSON schema for structured output.
        :param tools: Tools that model can use.
        :param max_retries: Maximum number of retries if the model failed to respond.
        :param delay_until_next_retry: Delay until next retry when failed.
        :return: The response from the language model. Keys: `response`, `reasoning`, `tool` (If tool call is made), `usage` (If supported)
        """
        pass

    @abstractmethod
    def tokenizer(self, histories: list[dict]) -> int:
        """
        Tokenize the conversation history and return the number of tokens.

        :param histories: The conversation history.
        :return: Number of tokens.
        """
        pass

    def send_request_ensure_structured(self, histories: list[dict], structure: dict, model_config: dict|None = None, tools: dict|None = None, max_retries_on_parse_fail: int = 3, delay_until_next_retry_on_parse_fail: float = 3.0, max_retries: int = 3, delay_until_next_retry: float = 3.0) -> dict|list|None:
        """
        Send a request to the language model driver and ensure the response is structured according to the provided schema.

        :param histories: The conversation history.
        :param model_config: Configuration for the language model inference such as temperature, top_p/k samplings, etc.
        :param structure: JSON schema for structured output.
        :param tools: Tools that model can use.
        :param max_retries_on_parse_fail: Maximum number of retries is not structured correctly.
        :param delay_until_next_retry_on_parse_fail: Delay until next retry when failed to respond in structured format.
        :param max_retries: Maximum number of retries if the model failed to respond.
        :param delay_until_next_retry: Delay until next retry when failed.
        :return: The structured response from the language model.
        """

        def continue_or_break(current_trial: int) -> bool:
            if current_trial < max_retries_on_parse_fail - 1:
                if self.DEBUG_MODE:
                    print(f"    [DEBUG] Failed to parse model response. Retrying... ({i + 1}/{max_retries_on_parse_fail})")
                time.sleep(delay_until_next_retry_on_parse_fail)
                return True
            else:
                return False

        for i in range(max_retries_on_parse_fail):
            try:
                model_response: dict = self.send_request(histories, model_config, structure, tools, max_retries, delay_until_next_retry)
                self.last_usage = model_response.get("usage") if model_response else None

                # Check model response
                if model_response is None or len(model_response) == 0:
                    if continue_or_break(i):
                        continue
                    else:
                        break

                # Try parsing
                if self.DEBUG_MODE:
                    print(f"    [DEBUG] Got non-empty response from model: {json.dumps(model_response, indent=4)}")
                model_text: str = model_response.get("response", "{}")
                parsed = json.loads(model_text)

                return parsed
            except json.decoder.JSONDecodeError:
                if continue_or_break(i):
                    continue
                else:
                    break

        return None
