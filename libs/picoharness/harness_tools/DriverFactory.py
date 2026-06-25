from libs.picoharness.struct.LMDriver import LMDriver

import importlib

def get_driver(model_preset: dict) -> LMDriver:
    # Required fields
    required_fields = ["context", "driver", "url", "model"]

    # Optional fields
    optional_fields = ["model-config"] # Ex. temperature, top_p, etc.

    # Check required fields
    for field in required_fields:
        if field not in model_preset:
            raise KeyError(f"Required field '{field}' is missing")

    # Import driver
    location: str = "libs.picoharness.drivers."
    driver_name = model_preset["driver"]
    module = importlib.import_module(location + driver_name)

    # From module, import the class with driver_name
    driver_class = getattr(module, driver_name)

    # Initialize with parameters
    context: int = model_preset.get("context", 4096)
    url: str = model_preset.get("url", "")
    model: str = model_preset.get("model", "")
    model_config = model_preset.get("model-config", {})
    driver_instance = driver_class(context, url, model, model_config)


    return driver_instance
