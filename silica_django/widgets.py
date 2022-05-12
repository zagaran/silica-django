import django.forms


class SilicaRenderer(django.forms.Widget):
    custom_component_name = None

    def __init__(self, *args, custom_component_name=None, **kwargs):
        super().__init__(*args, **kwargs)
        if custom_component_name:
            self.custom_component_name = custom_component_name


class SilicaSubmitRenderer(SilicaRenderer, django.forms.CharField):
    custom_component_name = "silica-submit-renderer"
