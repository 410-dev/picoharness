import importlib
import inspect
import json
import pkgutil
from pathlib import Path
from functools import lru_cache

from libs.picoharness.struct.LMTool import LMTool


TOOLS_PACKAGE = "libs.picoharness.lm_callable_tools"


@lru_cache(maxsize=1)
def _load_tools() -> dict[str, LMTool]:
    tools: dict[str, LMTool] = {}
    package = importlib.import_module(TOOLS_PACKAGE)

    # Namespace packages can be missed by pkgutil, so also scan Python files.
    module_names = set()
    for package_path in package.__path__:
        root = Path(package_path)
        for file_path in root.rglob("*.py"):
            if file_path.name == "__init__.py":
                continue
            relative = file_path.relative_to(root).with_suffix("")
            module_names.add(f"{package.__name__}.{'.'.join(relative.parts)}")

    for module_info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        if not module_info.ispkg:
            module_names.add(module_info.name)

    for module_name in sorted(module_names):
        module = importlib.import_module(module_name)
        for _, member in inspect.getmembers(module, inspect.isclass):
            # Only register concrete tool classes defined by the module itself.
            if member is LMTool or not issubclass(member, LMTool):
                continue
            if member.__module__ != module.__name__:
                continue

            tool: LMTool = member()
            meta = tool.meta()
            name = meta.get("name")
            if not name:
                raise ValueError(f"Tool {member.__name__} has no meta.name")
            tools[name] = tool

    return tools


def _normalize_action(action: dict) -> tuple[str, dict]:
    # Accept a few common tool-call shapes from local models and SDKs.
    name = (
        action.get("name")
        or action.get("tool")
        or action.get("tool_name")
        or action.get("function")
    )
    parameters = (
        action.get("parameters")
        or action.get("arguments")
        or action.get("args")
        or {}
    )

    if isinstance(name, dict):
        parameters = name.get("parameters") or name.get("arguments") or parameters
        name = name.get("name")

    if isinstance(parameters, str):
        parameters = json.loads(parameters)

    if not isinstance(name, str) or not name:
        raise ValueError("Tool call must include a tool name")
    if not isinstance(parameters, dict):
        raise ValueError("Tool call parameters must be a JSON object")

    return name, parameters


def execute(action: dict) -> str:
    name, parameters = _normalize_action(action)
    tools = _load_tools()

    if name not in tools:
        available = ", ".join(sorted(tools.keys()))
        raise ValueError(f"Unknown tool '{name}'. Available tools: {available}")

    print(f"[HARNESS] Executing tool [{name}] with parameters of {json.dumps(parameters)}")
    return tools[name].execute(parameters)


def enumerate_tools() -> str:
    return json.dumps(get_tools(), ensure_ascii=False, indent=2)


def get_tools(blacklisted: list[str] | None = None) -> dict:
    blacklist = set(blacklisted or [])
    tools = []

    for name, tool in sorted(_load_tools().items()):
        if name in blacklist:
            continue

        meta = tool.meta()
        # LM Studio uses the OpenAI-compatible function tool schema.
        tools.append({
            "type": "function",
            "function": {
                "name": meta["name"],
                "description": meta["description"],
                "parameters": meta["parameters"],
            },
        })

    return {"tools": tools}
