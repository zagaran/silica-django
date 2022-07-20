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

    def get_field_config(self, field_name):
        return self.config.get(field_name, None)


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
                 ui_format=None, readonly=None, multiple_of=None, title=None, examples=None, display_delete=False, 
                 enable_add=False, error_message=None, no_data_msg=None, static_title=None, add_text=None, 
                 max_item_text=None, css_classes=None, wrapper_css_classes=None):
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
