from typing import Dict, Any


class JsonSchemaUtils:
    @staticmethod
    def value_as_jsonschema(value) -> Dict[str, Any]:
        if type(value) == list:
            return {"enum": value}
        else:
            return {"const": value}
