from abc import abstractmethod, ABC


class LMTool(ABC):

    @abstractmethod
    def meta(self) -> dict:
        """
        Returns a dictionary with the following keys:
        - name: str
        - description: str
        - parameters: dict (JSON Schema)
        """
        pass

    @abstractmethod
    def execute(self, parameters: dict, local_config: dict|None = None) -> str:
        """
        Executes the tool with the given parameters and returns a string result.
        """
        pass

    def compatible(self, schema_version: int = 1) -> bool:
        """
        Checks if the tool is compatible with the given schema version.
        """
        if schema_version == 1:
            return self.schema_check_v1()
        return False

    def schema_check_v1(self) -> bool:
        """
        Checks if the tool's meta information is compatible with schema version 1.
        """
        meta = self.meta()
        required_keys: list[str] = ["name", "description", "parameters"]

        # 키 체크
        for key in required_keys:
            if key not in meta:
                print(f"Missing required key in meta: {key}")
                return False

        # 파라미터 구조 체크
        required_keys: list[str] = ["type", "properties", "required"]
        for key in meta.get("parameters", {}).keys():
            if key not in required_keys:
                print(f"Missing required key in parameters: {key}")
                return False

        # Properties 내부 구조 체크
        required_keys: list[str] = ["type", "description"]
        for key, value in meta.get("parameters", {}).get("properties", {}).items():

            # 각 property 안에 required_keys 를 충족하는지 체크
            for required_key in required_keys:
                if required_key not in value.keys():
                    print(f"Missing required key in parameters: {key}.{required_key}")
                    return False
                if value.get("type", "") not in ["string", "integer", "float", "boolean"]:
                    print(f"Invalid type in parameters: {key}.type = {value.get('type')}")
                    return False
                if value.get("description", "") == "":
                    print(f"Empty description in parameters: {key}.description")
                    return False

        # required 에 명시된 키들이 properties 에 존재하는지 체크
        for req_key in meta.get("parameters", {}).get("required", []):
            if req_key not in meta.get("parameters", {}).get("properties", {}):
                print(f"Required key {req_key} not found in properties")
                return False

        return True