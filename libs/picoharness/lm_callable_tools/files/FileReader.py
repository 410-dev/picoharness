from libs.picoharness.struct.LMTool import LMTool

import os

class FileReader(LMTool):

    def meta(self) -> dict:
        return {
            "name": "FileReader",
            "description": "Read file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file"
                    },
                },
                "required": ["file_path"]
            }
        }

    def execute(self, parameters: dict, local_config: dict|None = None) -> str:
        # Get file path
        file_path: str | None = parameters.get("file_path", None)
        if file_path is None:
            raise ValueError("file_path parameter is required")

        elif not os.path.isfile(file_path):
            raise ValueError(f"Provided path '{file_path}' is not a file or does not exist")

        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return content