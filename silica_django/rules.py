from silica_django.utils.jsonschema import JsonSchemaUtils


class UIEffects:
    show = "SHOW"
    hide = "HIDE"
    disable = "DISABLE"
    enable = "ENABLE"


class Condition(JsonSchemaUtils):
    arguments = None
    schema_key = None

    def __init__(self, *args):
        self.arguments = args

    def _get_schema_for_argument(self, arg):
        if isinstance(arg, Condition):
            return arg._get_condition_schema()
        elif isinstance(arg, dict):
            # if the argument is a dictionary, we are in a top-level case
            return {
                "type": "object",
                self.schema_key: [
                    {"properties": {key: self._get_schema_for_argument(val)}}
                    for key, val in arg.items()]
            }
        else:
            return self.value_as_jsonschema(arg)

    def _get_condition_schema(self):
        return {
            self.schema_key: [self._get_schema_for_argument(arg) for arg in self.arguments]
        }


class Or(Condition):
    schema_key = "anyOf"


class And(Condition):
    schema_key = "allOf"


class Not(Condition):
    schema_key = "not"

    def _get_condition_schema(self):
        return {
            self.schema_key: self._get_schema_for_argument(self.arguments)
        }


class Rule(JsonSchemaUtils):
    argument = None
    effect = None
    custom_schema = None

    def __init__(self, argument):
        # argument is either a dictionary or a Condition
        self.argument = argument

    def _get_schema_for_argument(self, arg):
        if isinstance(arg, Condition):
            return arg._get_condition_schema()
        else:
            # by default, behavior is an AND
            return self._get_schema_for_argument(And(self.argument))

    def get_schema(self, full_schema=True):
        if self.custom_schema:
            return self.custom_schema
        if full_schema:
            schema = {
                "effect": self.effect,
                "condition": {
                    "scope": "#",
                    "schema": self._get_schema_for_argument(self.argument)
                }
            }
        else:
            schema = self._get_schema_for_argument(self.argument)
        return schema


class ShowIf(Rule):
    effect = UIEffects.show


class HideIf(Rule):
    effect = UIEffects.hide


class DisableIf(Rule):
    effect = UIEffects.disable


class EnableIf(Rule):
    effect = UIEffects.enable
