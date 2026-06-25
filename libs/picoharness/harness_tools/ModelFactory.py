import json

from libs.picoharness.harness_tools import DriverFactory
from libs.picoharness.struct.LMDriver import LMDriver
from libs.picoharness.struct.LanguageModel import LanguageModel


def model_router(priority: str) -> str:
    valid_priorities = ["price", "intelligence", "balance", "length"]
    if priority not in valid_priorities:
        raise ValueError(f"Invalid priority: {priority} - Required any of: {'|'.join(valid_priorities)}" )

    with open("models.json", "r") as f:
        models = json.loads(f.read())

    model_keys: dict[str, int] = {}
    for model_name, model_values in models.items():
        if "priority" not in model_values:
            continue
        if model_values.get("priority", f"{priority}:0").startswith(f"{priority}:"):
            model_keys[model_name] = int(model_values["priority"].split(":")[1])
        else:
            continue

    # Sort by score - higher comes first
    sorted_models = sorted(model_keys.items(), key=lambda x: x[1], reverse=True)
    if not sorted_models:
        raise ValueError(f"No models found for priority: {priority}")

    return sorted_models[0][0]  # Return the model name with the highest score


def get_model_for(priority: str) -> LanguageModel:
    with open("models.json", "r") as f:
        models = json.loads(f.read())

    model_name = model_router(priority)
    driver: LMDriver = DriverFactory.get_driver(models[model_name])
    model: LanguageModel = LanguageModel().using(driver)
    return model
