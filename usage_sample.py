import json

from libs.picoharness.harness_tools import DriverFactory
from libs.picoharness.struct.LMDriver import LMDriver
from libs.picoharness.struct.LanguageModel import LanguageModel

def main():

    with open("models.json", "r") as f:
        models = json.loads(f.read())

    driver: LMDriver     = DriverFactory.get_driver(models["gemma4-pro"])
    driver.DEBUG_MODE = True
    model: LanguageModel = LanguageModel().using(driver)

    prompt: str          = "README.md 파일을 읽고 요약해주세요."
    response: str        = model.chat(prompt, use_tools=True).response()
    print(response)
    print()
    print(f"Used {model.token_usage().all()} tokens in total.")

if __name__ == "__main__":
    main()
