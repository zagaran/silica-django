import unittest

from silica_django.config import SilicaConfig, SilicaFieldConfig
from silica_django.utils.jsonschema import JsonSchemaUtils

from silica_django.rules import Or, And, Not, ShowIf


class BaseTestCase(unittest.TestCase):
    # set maximum number of characters which will be printed for a single diff
    maxDiff = 10000

    def assertEqualAsStrings(self, first, second, msg=None):
        """ Converts arguments to strings before comparing them; helps with legibility when reading printout from 
        comparing heavily nested objects """
        return self.assertEqual(str(first), str(second), msg=msg)


class TestConditions(BaseTestCase):
    def test_or_single_key_single_value(self):
        or_1 = Or(key1=1)
        self.assertEqualAsStrings(or_1.get_condition_schema(), {
            "anyOf": [
                {"type": "object", "properties": {"key1": {"const": 1}}}
            ]
        })

    def test_or_single_key_multiple_values(self):
        or_1 = Or(key1=[1, 2, 3])
        self.assertEqualAsStrings(or_1.get_condition_schema(), {
            "anyOf": [
                {"type": "object",
                 "properties": {"key1": {"enum": [1, 2, 3]}}}
            ]
        })

    def test_or_multiple_keys(self):
        or_1 = Or(key1=1, key2=[1, 2, 3])
        self.assertEqualAsStrings(or_1.get_condition_schema(), {
            "anyOf": [
                {
                    "type": "object",
                    "properties": {"key1": {"const": 1}, "key2": {"enum": [1, 2, 3]}}
                }
            ]
        })

    def test_and_multiple_keys(self):
        and_1 = And(key1=1, key2=2)
        self.assertEqualAsStrings(and_1.get_condition_schema(), {
            "allOf": [
                {
                    "type": "object",
                    "properties": {
                        "key1": {"const": 1},
                        "key2": {"const": 2}
                    }
                }
            ]
        })

    def test_not(self):
        not_1 = Not(key1=1)
        self.assertEqualAsStrings(not_1.get_condition_schema(), {
            'not': {
                'type': 'object',
                'properties':
                    {
                        'key1': {'const': 1}
                    }
            }
        })

    def test_not_composable(self):
        not_1 = Not(Or(key1=1, key2=1))
        self.assertEqualAsStrings(not_1.get_condition_schema(), {
            'not': {
                'anyOf': [
                    {
                        'type': 'object',
                        'properties': {
                            'key1': {'const': 1},
                            'key2': {'const': 1},
                        }
                    }
                ]
            }
        })


class TestRules(BaseTestCase):
    def test_show_only_kwargs(self):
        rule = ShowIf(key1=1)
        self.assertEqualAsStrings(rule.get_rule_schema(), {
            "effect": rule.effect,
            "condition": {
                "scope": "#",
                "schema": {
                    "anyOf": [
                        {
                            "allOf": [
                                {
                                    "type": "object",
                                    "properties": {
                                        "key1": {"const": 1}
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        })

    def test_show_only_args(self):
        rule = ShowIf(Or(key1=1, key2=1), And(key1=2, key2=3))
        self.assertEqualAsStrings(rule.get_rule_schema(), {
            "effect": rule.effect,
            "condition": {
                "scope": "#",
                "schema": {
                    "anyOf": [
                        {
                            "anyOf": [
                                {
                                    "type": "object",
                                    "properties": {
                                        "key1": {"const": 1},
                                        "key2": {"const": 1},
                                    }
                                }
                            ]
                        },
                        {
                            "allOf": [
                                {
                                    "type": "object",
                                    "properties": {
                                        "key1": {"const": 2},
                                        "key2": {"const": 3},
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        })

    def test_show_args_and_kwargs(self):
        rule = ShowIf(And(key2=2, key3=3), key1=1)
        self.assertEqualAsStrings(rule.get_rule_schema(), {
            "effect": rule.effect,
            "condition": {
                "scope": "#",
                "schema": {
                    "anyOf": [
                        {
                            "allOf": [
                                {
                                    "type": "object",
                                    "properties": {
                                        "key2": {"const": 2},
                                        "key3": {"const": 3},
                                    }
                                }
                            ]
                        },
                        {
                            "allOf": [
                                {
                                    "type": "object",
                                    "properties": {
                                        "key1": {"const": 1}
                                    }
                                }
                            ]
                        },
                    ]
                }
            }
        })


class TestJsonSchemaTranslation(BaseTestCase):

    def test_value_as_jsonschema(self):
        self.assertEqualAsStrings(JsonSchemaUtils.value_as_jsonschema(1), {"const": 1})
        self.assertEqualAsStrings(JsonSchemaUtils.value_as_jsonschema([1]), {"enum": [1]})


class TestSilicaConfig(BaseTestCase):
    def assertKwargsCorrectlyProcessed(self):
        """ Assert that the kwargs passed to the SilicaConfig are properly formatted internally """
        config = SilicaConfig(
            field1=SilicaFieldConfig(
                maximum=1,
                minimum=2,
                default=2,
                min_length=1,
                max_length=3,
                description="a description",
                type="object",
                schema_format="int",
                required=["field2"],
                additional_properties=True,
                label="oh yeah",
            )
        )
        
        
        return True
    
    def assertUISchemaCustomize(self):
        return True
    
    def assertUISchemaOverride(self):
        return True
    
    def assertSchemaCustomize(self):
        return True
    
    def assertSchemaOverride(self):
        return True
    
    def assertRule(self):
        return True
    
    def assertComplexUISchema(self):
        return True

if __name__ == "__main__":
    unittest.main()
