# 프로젝트 규칙

## 언어

* 공개 함수와 클래스 메서드에는 Python 타입 힌트를 사용합니다.
* 모듈은 작고 목적에 맞게 유지합니다.
* 더 강력한 추상화가 필요해지기 전까지는 명시적인 딕셔너리와 단순한 데이터 구조를 선호합니다.
* 주석은 짧게 작성하고, 명확하지 않은 동작을 설명할 때만 사용합니다.

## 패키지 구조

* 언어 모델 드라이버는 `libs/picoharness/drivers`에 둡니다.
* 기본 인터페이스와 재사용 가능한 구조는 `libs/picoharness/struct`에 둡니다.
* 하네스 수준의 헬퍼는 `libs/picoharness/harness_tools`에 둡니다.
* 모델이 호출할 수 있는 도구는 `libs/picoharness/lm_callable_tools`에 둡니다.
* 하네스에 특화되지 않은 범용 헬퍼는 `libs/utilities`에 둡니다.

## 드라이버

모든 드라이버는 반드시 `LMDriver`를 상속하고 다음을 구현해야 합니다.

* `send_request(histories, model_config=None, structure=None, tools=None, ...)`
* `tokenizer(histories)`

드라이버 응답은 다음과 같은 정규화된 형태를 사용해야 합니다.

```python
{
    "response": "assistant-visible text",
    "reasoning": "optional reasoning text",
    "tool": "{\"name\": \"ToolName\", \"parameters\": {}}",
    "usage": {
        "input": 0,
        "output": 0,
        "reasoning": 0
    }
}
```

실제로 도구 호출이 요청된 경우에만 `tool`을 포함합니다.
드라이버 또는 제공자가 토큰 사용량을 보고하는 경우에만 `usage`를 포함합니다.

### `DriverFactory.get_driver` 사용 템플릿

드라이버 인스턴스는 직접 생성하지 말고 `DriverFactory.get_driver(model_preset)`을 통해 생성합니다.
`model_preset`은 보통 `models.json`에서 읽어 온 개별 모델 프리셋 딕셔너리입니다.

```python
import json

from libs.picoharness.harness_tools import DriverFactory
from libs.picoharness.struct.LMDriver import LMDriver

with open("models.json", "r", encoding="utf-8") as f:
    models: dict = json.load(f)

model_preset: dict = models["preset-name"]
driver: LMDriver = DriverFactory.get_driver(model_preset)
```

프리셋의 `driver` 값은 `libs/picoharness/drivers` 아래의 모듈명과 클래스명과 같아야 합니다.
예를 들어 `"driver": "OpenAIDriver"`를 사용하면 `libs.picoharness.drivers.OpenAIDriver` 모듈에서 `OpenAIDriver` 클래스를 가져옵니다.

`DriverFactory.get_driver`에 전달하는 프리셋에는 다음 필수 필드가 있어야 합니다.

* `context`
* `driver`
* `url`
* `model`

모델별 온도, top-p 같은 선택 설정은 `model-config` 딕셔너리에 둡니다.

## 도구

호출 가능한 모든 도구는 반드시 `LMTool`을 상속해야 합니다.

도구 메타데이터에는 다음이 포함되어야 합니다.

* `name`
* `description`
* JSON Schema 객체 형식의 `parameters`

도구 실행 규칙은 다음과 같습니다.

* 작업을 수행하기 전에 필수 파라미터를 검증합니다.
* 일반 문자열을 반환합니다.
* 사용자 또는 모델 입력이 유효하지 않은 경우 `ValueError`를 발생시킵니다.
* 도구의 이름과 설명이 명확하게 부작용을 암시하지 않는 한, 부작용은 피합니다.

### `LMTool.meta()` 작성 방법

`meta()`는 모델에게 노출할 도구 명세를 반환합니다. 반환값은 반드시 `name`, `description`, `parameters`를 포함합니다.

```python
from libs.picoharness.struct.LMTool import LMTool


class ExampleTool(LMTool):

    def meta(self) -> dict:
        return {
            "name": "ExampleTool",
            "description": "Explain clearly what this tool does",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query or input text"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results"
                    }
                },
                "required": ["query"]
            }
        }

    def execute(self, parameters: dict, local_config: dict | None = None) -> str:
        query: str | None = parameters.get("query")
        if query is None:
            raise ValueError("query parameter is required")

        limit: int = parameters.get("limit", 10)
        return f"query={query}, limit={limit}"
```

`parameters`는 JSON Schema 객체 형식을 사용하되, 현재 호환성 검사 기준에서는 다음 구조를 지킵니다.

* 최상위 `parameters.type`은 `"object"`로 둡니다.
* `properties`에는 각 파라미터 이름을 키로 두고 `type`과 `description`을 작성합니다.
* 각 파라미터 `type`은 `"string"`, `"integer"`, `"float"`, `"boolean"` 중 하나를 사용합니다.
* 필수 파라미터는 `required` 배열에 넣고, `required`에 넣은 이름은 반드시 `properties`에도 있어야 합니다.
* 선택 파라미터는 `required`에서 제외하고, 필요하면 `default`를 함께 적습니다.

도구 이름은 클래스명과 동일하게 두는 것을 기본으로 합니다. 설명은 모델이 호출 여부를 판단할 수 있도록 동작, 입력 의미, 부작용 여부를 짧고 구체적으로 씁니다.

## 모델 프리셋

각 `models.json` 프리셋에는 다음이 포함되어야 합니다.

* `context`
* `driver`
* `url`
* `model`

선택적인 모델 추론 설정은 `model-config` 아래에 둡니다.

## 오류 처리

* 문제의 원인에 가까운 위치에서 명확한 예외를 발생시킵니다.
* 알 수 없는 드라이버나 도구 이름을 거부할 때는 사용 가능한 옵션을 함께 포함합니다.
* 재시도 로직은 `LanguageModel`이 아니라 드라이버 내부에 둡니다.

## 문서화

* 설정 방법, 실행 명령어, 프로젝트 구조가 변경되면 `README.md`를 업데이트합니다.
* 새로운 반복 패턴을 추가할 때는 이 규칙 파일을 업데이트합니다.
* 예제는 `usage_sample.py` 또는 작은 독립 실행 스크립트에 복사해 사용할 수 있는 형태를 선호합니다.
