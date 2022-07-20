from django import forms

from silica_django import fields
from silica_django.fields import SilicaSubFormArrayField
from silica_django.utils.jsonschema import JsonSchemaUtils
from silica_django.widgets import SilicaRenderer


class JsonSchemaMixin(JsonSchemaUtils):
    """ Contains utility functions for interfacing between native python/django and jsonschema """
    def _django_to_jsonschema_field(self, field_name, field, field_config=None):
        # most field types are string by default
        field_type = "string"
        # format is only required for some special types e.g. date
        field_kwargs = {
            'name': field_name,
            'options': {}
        }
        if isinstance(field, forms.DateField):
            field_kwargs["format"] = "date"
        elif isinstance(field, forms.DateTimeField):
            field_kwargs["format"] = "date-time"
        elif isinstance(field, forms.TimeField):
            field_kwargs["format"] = "time"
        elif isinstance(field, forms.IntegerField):
            field_type = "integer"
        elif isinstance(field, forms.FloatField) or isinstance(field, forms.DecimalField):
            field_type = "number"
        elif isinstance(field, forms.BooleanField):
            field_type = "boolean"
        # todo: differentiate between arrays of related items and a multi field (e.g. tags)
        elif isinstance(field, fields.SilicaSubFormArrayField):
            field_type = "array"
            if field._instantiated_forms:
                item_schema = field._instantiated_forms[0].get_data_schema()
            else:
                # there are no existing sub-items, instantiate the form to get the schema
                item_schema = field._instantiate_form().get_data_schema()
            item_schema["properties"][field.identifier_field] = {
                    "type": "number",
                    "hidden": True
                }
            field_kwargs['items'] = {
                **item_schema,
            }
        if hasattr(field, 'choices'):
            field_kwargs["oneOf"] = [{'const': value, 'title': title} for (value, title) in field.choices]
        # special checks
        if isinstance(field.widget, forms.HiddenInput):
            field_kwargs['hidden'] = True
        if field.disabled:
            field_kwargs['readOnly'] = True
        if isinstance(field.widget, forms.RadioSelect):
            # for a radio select, everything is a string - we'll convert on the backend
            field_type = "string"
            if not hasattr(field, 'choices'):
                field_kwargs["oneOf"] = [{'const': str(value), 'title': title} for (value, title) in field.widget.choices]
        if field_config:
            if field_config.schema:
                field_kwargs.update(field_config.schema)
        if isinstance(field, SilicaSubFormArrayField):
            if field.min_instances:
                field_kwargs['minItems'] = field.min_instances
            if field.max_instances:
                field_kwargs['maxItems'] = field.max_instances
        # if the field is not required, then null/blank is a valid option
        if not field.required:
            # allow null
            field_type = [field_type, 'null']
            # allow blank
            field_kwargs['minLength'] = 0
        return {
            "type": field_type,
            **field_kwargs
        }

    def _django_widget_to_ui_schema(self, field, field_config=None):
        ui_schema = {
            'options': {}
        }
        if field.label:
            ui_schema['label'] = field.label
        if field.disabled:
            ui_schema['readonly'] = True
        # special values for widgets
        if isinstance(field.widget, forms.Textarea):
            ui_schema['options']['multi'] = True
        if isinstance(field.widget, SilicaRenderer):
            ui_schema['options']['customComponentName'] = field.widget.custom_component_name
        if isinstance(field.widget, forms.RadioSelect):
            ui_schema['options']['format'] = "radio"
        # add rules and update uischema
        if field_config:
            if field_config.rule:
                ui_schema['rule'] = field_config.rule.get_ui_schema()
            if field_config.uischema:
                ui_opts = ui_schema['options']
                ui_opts.update(field_config.uischema['options'])
                ui_schema.update(field_config.uischema)
                ui_schema['options'] = ui_opts
        return ui_schema
