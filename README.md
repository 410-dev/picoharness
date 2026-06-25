# blogger-v2 / picoharness

`blogger-v2`는 로컬 언어 모델과 Python 기반 호출 도구를 실험하기 위한 작은 워크스페이스입니다. 핵심 패키지인 `libs.picoharness`는 모델 드라이버를 `LanguageModel` 인터페이스 뒤에 숨기고, 모델이 필요한 경우 로컬 도구를 호출할 수 있도록 하네스를 제공합니다.

## 프로젝트 구조

```text
.
|-- libs/
|   |-- picoharness/
|   |   |-- drivers/              # 언어 모델 드라이버 구현체
|   |   |-- harness_tools/        # DriverFactory 같은 하네스 보조 도구
|   |   |-- lm_callable_tools/    # 모델이 호출할 수 있는 도구
|   |   |-- struct/               # 기본 인터페이스와 공통 구조
|   |   `-- harness.py            # 도구 탐색 및 실행 진입점
|   `-- utilities/                # 범용 유틸리티 모듈
|-- models.json                   # 모델 프리셋
|-- pyproject.toml                # Python 프로젝트 메타데이터와 의존성
|-- usage_sample.py               # 최소 실행 예제
`-- uv.lock                       # 고정된 의존성 정보
```

## 요구 사항

- Python 3.14 이상
- `uv`
- OpenAI 호환 API가 켜진 LM Studio 서버

의존성 설치:

```powershell
uv sync
```

## 모델 설정

모델 프리셋은 `models.json`에 정의합니다.

```json
{
  "gemma4-flash": {
    "context": 81920,
    "driver": "LMStudio",
    "url": "100.95.10.27",
    "model": ""
  }
}
```

`LMStudio` 드라이버의 `url`에는 `http://localhost:1234` 같은 전체 URL이나 IP/호스트만 넣을 수 있습니다. 포트를 생략하면 LM Studio의 기본 OpenAI 호환 API 포트인 `1234`를 사용합니다.

## 예제 실행

```powershell
uv run python usage_sample.py
```

예제는 `models.json`에서 모델 프리셋을 읽고, `LMStudio` 드라이버를 만든 뒤 `LanguageModel`에 연결합니다. `use_tools=True`로 호출하면 모델이 필요한 도구를 선택해서 사용할 수 있습니다.

## 도구 호출 구조

모델 호출 도구는 `libs/picoharness/lm_callable_tools` 아래에서 자동으로 탐색됩니다. 새 도구를 추가하려면 `LMTool`을 상속하고 다음 두 메서드를 구현합니다.

- `meta()`: 도구 이름, 설명, JSON Schema 파라미터를 반환합니다.
- `execute(parameters, local_config=None)`: 도구를 실행하고 문자열 결과를 반환합니다.

현재 포함된 도구:

- `EnumDirectory`: 디렉터리 안의 파일과 폴더를 나열합니다.
- `FileReader`: 텍스트 파일을 읽습니다.

## 기본 사용법

```python
from libs.picoharness.harness_tools import DriverFactory
from libs.picoharness.struct.LanguageModel import LanguageModel

driver = DriverFactory.get_driver(model_preset)
model = LanguageModel().using(driver)

response = model.chat("List files in my Documents directory", use_tools=True).response()
```

## 주요 동작

- `LMStudio`는 `/v1/chat/completions` 엔드포인트를 사용합니다.
- 도구 호출은 내부적으로 `{"name": "...", "parameters": {...}}` 형태로 정규화됩니다.
- 도구 실행 결과는 대화 히스토리에 다시 넣어 모델이 최종 답변을 이어서 만들 수 있게 합니다.
- 모델 응답에 `tool_calls`가 있으면 우선 사용하고, 일부 로컬 모델이 JSON 문자열로 도구 호출을 반환하는 경우도 보조적으로 처리합니다.

## 토큰 사용량 확인

드라이버가 토큰 사용량을 지원하면 `LanguageModel`이 요청별 사용량을 누적합니다.

```python
usage = model.token_usage()

usage.inputs()       # 누적 입력 토큰
usage.outputs()      # 누적 출력 토큰, reasoning 포함
usage.reasoning()    # 누적 reasoning 출력 토큰
usage.output_only()  # reasoning을 제외한 출력 토큰
usage.all()          # 입력 + 출력 전체 토큰
```

현재 `LMStudio` 드라이버는 OpenAI 호환 응답의 `usage.prompt_tokens`, `usage.completion_tokens`, `usage.completion_tokens_details.reasoning_tokens`를 읽어 사용량을 정규화합니다.

## 개발 규칙

자세한 코딩 규칙과 확장 방식은 `Convention.md`를 참고하세요.
