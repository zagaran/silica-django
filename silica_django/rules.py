from silica_django.utils.jsonschema import JsonSchemaUtils


class UIEffects:
    show = "SHOW"
    hide = "HIDE"
    disable = "DISABLE"
    enable = "ENABLE"


class Condition(JsonSchemaUtils):
    """
    Conditions take the following form:
        Condition(key1=value1, key2=value2, ...)
    Examples:
        And(key1=1, key2='and') -> evaluates to True if key1 == 1 and key2 == 'and'
        Or(key1=1, key2=2) -> evaluates to True if key1 == 1 or key2 == 2
    Conditions are also composable, e.g.
        Or(And(key1=1, key2=1), key2=3) -> evaluates to True if (key1 == 1 and key2 == 1) or key2 == 3

    The JsonSchema Condition spec is here: https://json-schema.org/understanding-json-schema/reference/combining.html

    """

    args = None
    schema_key = None
    kwargs = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def get_condition_schema(self):
        schema = []
        if self.args:
            schema = self._process_args()
        if self.kwargs:
            schema.append(self._process_kwargs())
        return {
            self.schema_key: schema
        }

    def _process_kwargs(self):
        # kwargs are direct assignments of keys to values, so we can just return a dictionary
        return {
            "type": "object",
            "properties": {key: self.value_as_jsonschema(val) for key, val in self.kwargs.items()}
        }

    def _process_args(self):
        # args can only be other conditions
        return [
            arg.get_condition_schema() for arg in self.args
        ]


class Or(Condition):
    schema_key = "anyOf"


class And(Condition):
    schema_key = "allOf"


class Not(Condition):
    schema_key = "not"

    def get_condition_schema(self):
        # the Not JsonSchema object has to be specially formatted
        schema = {}
        if self.kwargs:
            schema.update({
                **self._process_kwargs(),
            })
        for arg in self.args:
            schema.update(**arg.get_condition_schema())
        return {
            self.schema_key: schema
        }


class Rule(JsonSchemaUtils):
    """
        Rules take in any number of conditions as args; any kwargs are treated as a single And, i.e. And(**kwargs)

        In order to support this behavior, all conditions are wrapped in an Or.
    """
    args = None
    effect = None
    custom_schema = None
    kwargs = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def get_rule_schema(self):
        schema_args = []
        if len(self.args):
            schema_args += list(self.args)
        if len(self.kwargs):
            schema_args.append(And(**self.kwargs))
        schema = Or(*schema_args).get_condition_schema()
        return {
            "effect": self.effect,
            "condition": {
                "scope": "#",
                "schema": schema
            }
        }


class ShowIf(Rule):
    effect = UIEffects.show


class HideIf(Rule):
    effect = UIEffects.hide


class DisableIf(Rule):
    effect = UIEffects.disable


class EnableIf(Rule):
    effect = UIEffects.enable
