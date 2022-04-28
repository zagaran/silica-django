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

    def get_schema(self, rules, fields=None, uischema_options=None):
        if self.field_name in rules:
            self.kwargs['rule'] = rules[self.field_name].get_schema()
        if fields and self.field_name in fields:
            self.kwargs.update(self._django_widget_to_ui_schema(self.field_name, fields[self.field_name], rules=rules, uischema_options=uischema_options))
        return self.kwargs


class SilicaLayout(SilicaUiElement):
    elements = None

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
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

    def get_schema(self, rules, fields=None, uischema_options=None):
        schema = self.kwargs
        # flatten elements
        schema['elements'] = [element.get_schema(rules, fields=fields, uischema_options=uischema_options) for element in self.elements]
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

    def get_schema(self, rules, fields=None, uischema_options=None):
        if any([e.type != SilicaUiElementType.category for e in self.elements]):
            raise Exception("Categorization elements may not have any non-Category direct children.")
        return super().get_schema(rules, fields=fields, uischema_options=uischema_options)


class Category(SilicaLayout):
    type = SilicaUiElementType.category
    label = None

    def __init__(self, label, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kwargs.update({'label': label})
