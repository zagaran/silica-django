import random
import string

from silica_django.mixins import JsonSchemaMixin


class SilicaUiElementType:
    horizontal = "HorizontalLayout"
    vertical = "VerticalLayout"
    group = "Group"
    category = "Category"
    categorization = "Categorization"
    control = "Control"
    custom_element = "CustomHTMLElement"


class SilicaUiElement:
    type = None
    kwargs = None
    field_name = None

    def __init__(self, *args, **kwargs):
        if self.kwargs is None:
            self.kwargs = {
                **kwargs
            }
            
    def get_ui_schema(self, silica_form):
        raise NotImplemented


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

    def get_ui_schema(self, silica_form):
        field_config = silica_form.get_field_config(self.field_name)
        if field_config:
            if field_config.rule:
                self.kwargs['rule'] = field_config.rule.get_ui_schema()
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

    def get_all_elements(self):
        """ Returns all LayoutElements in a flat array; for use when nesting is not important, e.g. setting up mappings """
        elems = []
        for item in self.elements:
            if isinstance(item, SilicaLayout):
                elems.extend(item.get_all_elements())
            elif isinstance(item, SilicaUiElement):
                elems.append(item)
            else:
                raise Exception(f"Unsupported element {item}")
        return elems

    def get_ui_schema(self, silica_form):
        schema = self.kwargs
        # flatten elements
        schema['elements'] = [element.get_ui_schema(silica_form) for element in self.elements]
        if self.rule:
            schema['rule'] = self.rule.get_ui_schema()
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

    def get_ui_schema(self, silica_form):
        if any([e.type != SilicaUiElementType.category for e in self.elements]):
            raise Exception("Categorization elements may not have any non-Category direct children.")
        return super().get_ui_schema(silica_form)


class Category(SilicaLayout):
    type = SilicaUiElementType.category
    label = None

    def __init__(self, label, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kwargs.update({'label': label})


class CustomHTMLElement(SilicaUiElement):
    type = SilicaUiElementType.custom_element
    content = None
    rule = None
    _id = None

    def __init__(self, content, *args, **kwargs):
        super().__init__(*args, **kwargs)
        letters = string.ascii_lowercase
        self._id = ''.join(random.choice(letters) for _ in range(10))
        self.kwargs.update({
            'name': self._id,
            'type': self.type,
            'scope': '#/'
        })
        self.kwargs.update(kwargs)
        self.content = content

    def get_mapped_content(self):
        """ returns a dictionary of this element's generated id to the content it should render """
        return {self._id: self.content}

    def get_ui_schema(self, silica_form):
        schema = self.kwargs
        if self.rule:
            schema['rule'] = self.rule.get_ui_schema(silica_form)
        return schema
