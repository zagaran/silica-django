from copy import deepcopy

from django.forms import Widget, Field

from silica_django.templating import template_from_string


class SilicaConfig:
    """
        A SilicaConfig object contains all the Silica-specific configuration options for the form as a whole.
        For now, no configuration is available, but planned features include the ability to set the JSONForms
        validation mode.
    """

    config = None

    def __init__(self, **kwargs):
        if self.config is None:
            self.config = {}
        # key is field_name, value is SilicaFieldConfig for that field
        self.config.update(kwargs)

    def _get_field_config(self, field_name):
        return self.config.get(field_name, None)

    def get_field_config(self, field_name, render_context=None):
        """
        Args:
            field_name: name of field which config object is attached to

        Keyword Args:
            render_context: if None, indicates that config is not being used for display (e.g. for generating a Rule). 
                     If not none, used to format all valid strings in the schema and uischema (e.g. label, default)

        Returns:
            SilicaFieldConfig or None
        """
        config = self._get_field_config(field_name)
        if config:
            return config.process(render_context)
        return config


class SilicaFieldConfig:
    """
        A SilicaFieldConfig object contains all the Silica-specific configuration options
        for a control. Note that this is used to update and override the generated
        schema, but all fields are optional; a silica-powered form will always generate
        enough for a functional render on its own.
    """

    rule = None
    schema = None
    uischema = None

    def __init__(self, rule=None, maximum=None, minimum=None, default=None, min_length=None,
                 max_length=None, description=None, type=None, schema_format=None, label=None,
                 scope=None, ui_options=None, detail=None, show_sort_buttons=None, element_label_prop=None,
                 ui_format=None, readonly=None, multiple_of=None, title=None, examples=None, display_delete=None,
                 enable_add=None, error_message=None, no_data_msg=None, static_title=None, add_text=None,
                 max_item_text=None, css_classes=None, wrapper_css_classes=None, required=None,
                 additional_properties=None):
        # build kwargs into the uischema and schema objects formatted as jsonschema expects
        self.rule = rule
        schema = {
            'maximum': maximum,
            'minimum': minimum,
            'default': default,
            'minLength': min_length,
            'maxLength': max_length,
            'description': description,
            'type': type,
            'format': schema_format,
            'multipleOf': multiple_of,
            'examples': examples,
            'title': title,
            'errorMessage': error_message,
            'required': required,
            'additionalProperties': additional_properties
        }
        uischema_options = ui_options
        uischema = {
            'label': label,
            'scope': scope,
            'options': {
                'detail': detail,
                'showSortButtons': show_sort_buttons,
                'elementLabelProp': element_label_prop,
                'format': ui_format,
                # silica custom UISchema properties
                'readOnly': readonly,
                'displayDelete': display_delete,
                'enableAddButton': enable_add,
                'noDataMsg': no_data_msg,
                'staticTitle': static_title,
                'addText': add_text,
                'maxItemText': max_item_text,
                'overrideCss': css_classes,
                'wrapperOverrideCss': wrapper_css_classes,
            }
        }
        if uischema_options:
            uischema['options'].update(uischema_options)
        self.schema = {k: v for k, v in schema.items() if v is not None}
        uischema['options'] = {k: v for k, v in uischema['options'].items() if v is not None}
        self.uischema = {k: v for k, v in uischema.items() if v is not None}

    def process(self, context):
        processed_conf = deepcopy(self)

        def try_apply_context(root, key):
            try:
                root[key] = template_from_string(root[key]).render(context)
            except Exception:
                pass

        for key in processed_conf.schema:
            try_apply_context(processed_conf.schema, key)
        # ui schema is nested, so we have to be a bit more verbose
        try_apply_context(processed_conf.uischema, 'label')
        try_apply_context(processed_conf.uischema, 'scope')
        for key in processed_conf.uischema['options']:
            try_apply_context(processed_conf.uischema['options'], key)
        return processed_conf
