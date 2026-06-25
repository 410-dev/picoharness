from libs.picoharness.struct.LMTool import LMTool

import os

class EnumDirectory(LMTool):

    def meta(self) -> dict:
        return {
            "name": "EnumDirectory",
            "description": "List contents in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Path to the directory"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list contents recursively (default: false)",
                        "default": False
                    }
                },
                "required": ["dir_path"]
            }
        }

    def execute(self, parameters: dict, local_config: dict|None = None) -> str:
        # Get dir path
        dir_path: str | None = parameters.get("dir_path", None)
        if dir_path is None:
            raise ValueError("dir_path parameter is required")

        elif not os.path.isdir(dir_path):
            raise ValueError(f"Provided path '{dir_path}' is not a directory or does not exist")

        # List contents
        contents = os.listdir(dir_path)

        # Format it
        result_format_line = "[%TYPE%] %NAME% (Modified: %MODIFIED% / Created: %CREATED%)"
        result_lines = []
        for item in contents:
            item_path = os.path.join(dir_path, item)
            item_type = "Directory" if os.path.isdir(item_path) else "File"
            modified_time = os.path.getmtime(item_path)
            created_time = os.path.getctime(item_path)

            result_line = result_format_line.replace("%TYPE%", item_type)
            result_line = result_line.replace("%NAME%", item)
            result_line = result_line.replace("%MODIFIED%", str(modified_time))
            result_line = result_line.replace("%CREATED%", str(created_time))
            result_lines.append(result_line)

        return "\n".join(result_lines)

