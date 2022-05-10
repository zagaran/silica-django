from silica_django.mixins import JsonSchemaMixin


class SilicaUiElementType:
    horizontal = "HorizontalLayout"
    vertical = "VerticalLayout"
    group = "Group"
    category = "Category"
    categorization = "Categorization"
    control = "Control"


class SilicaUiElement:
    type = None
    kwargs = None
    field_name = None

    def __init__(self, **kwargs):
        if self.kwargs is None:
            self.kwargs = {
                **kwargs
            }


class Control(SilicaUiElement, JsonSchemaMixin):
    type = SilicaUiElementType.control

    def __init__(self, field_name, scope=None, **kwargs):
        self.field_name = field_name
        super().__init__(**kwargs)
        if scope is None:
            scope = f'#/properties/{field_name.lower()}'
        self.kwargs.update({
            'scope': scope,
            'type': self.type,
            'field_name': field_name,
        })
        self.kwargs.update(kwargs)

    def get_schema(self, silica_form):
        field_config = silica_form.get_field_config(self.field_name)
        if field_config:
            if field_config.rule:
                self.kwargs['rule'] = field_config.rule.get_schema()
            self.kwargs.update(self._django_widget_to_ui_schema(silica_form.fields[self.field_name], field_config=field_config))
        else:
            self.kwargs.update(self._django_widget_to_ui_schema(silica_form.fields[self.field_name]))
        return self.kwargs


class SilicaLayout(SilicaUiElement):
    elements = None
    rule = None

    def __init__(self, *args, rule=None, **kwargs):
        super().__init__(**kwargs)
        self.rule = rule
        # args should be a list of SilicaUiElements
        self.elements = [self._process_arg(a) for a in args]
        self.kwargs.update({'type': self.type})

    @staticmethod
    def _process_arg(arg):
        # if arg is a SilicaUiElement, we are recursing through a layout; if it is a string, we have to construct a Control
        if type(arg) == str:
            return Control(arg)
        elif isinstance(arg, SilicaUiElement):
            return arg
        else:
            raise Exception(f"Unhandled type {type(arg)}")

    def get_schema(self, silica_form):
        schema = self.kwargs
        # flatten elements
        schema['elements'] = [element.get_schema(silica_form) for element in self.elements]
        if self.rule:
            schema['rule'] = self.rule.get_schema()
        return schema


class HorizontalLayout(SilicaLayout):
    type = SilicaUiElementType.horizontal


class VerticalLayout(SilicaLayout):
    type = SilicaUiElementType.vertical


class Group(SilicaLayout):
    type = SilicaUiElementType.group

    def __init__(self, label, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kwargs.update({'label': label})


class Categorization(SilicaLayout):
    type = SilicaUiElementType.categorization

    def get_schema(self, silica_form):
        if any([e.type != SilicaUiElementType.category for e in self.elements]):
            raise Exception("Categorization elements may not have any non-Category direct children.")
        return super().get_schema(silica_form)


class Category(SilicaLayout):
    type = SilicaUiElementType.category
    label = None

    def __init__(self, label, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kwargs.update({'label': label})
