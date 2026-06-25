from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Any

def run_threading(
    runnable: Callable[..., Any],
    parameters: dict,
    thread_count: int,
    raise_error: bool = False,
) -> dict:
    """
    스레딩을 처리하며 결과를 반환합니다.

    parameters 예시:
        {
            "label1": value,              # runnable(value)
            "label2": (arg1, arg2),       # runnable(arg1, arg2)
            "label3": {"a": 1, "b": 2},   # runnable(a=1, b=2)
        }

    :param runnable: 실행할 함수
    :param parameters: label -> arguments 매핑
    :param thread_count: 스레드 수
    :param raise_error: True면 작업 중 예외 발생 시 그대로 raise
    :return: {label: result}
    """
    results = {}

    def submit_task(x, param):
        if isinstance(param, tuple):
            return x.submit(runnable, *param)

        if isinstance(param, dict):
            return x.submit(runnable, **param)

        return x.submit(runnable, param)

    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        future_to_label = {
            submit_task(executor, param): label
            for label, param in parameters.items()
        }

        for future in as_completed(future_to_label):
            label = future_to_label[future]

            try:
                results[label] = future.result()
            except Exception as e:
                if raise_error:
                    raise

                results[label] = e

    return results