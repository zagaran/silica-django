import random
import string

from django.template import engines
from django.template.exceptions import TemplateSyntaxError, TemplateDoesNotExist

from silica_django.mixins import JsonSchemaMixin
from silica_django.templating import template_from_string


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

    def __repr__(self):
        return f"{self.type}: {self.field_name}"

    def get_ui_schema(self):
        raise NotImplemented


class Control(SilicaUiElement, JsonSchemaMixin):
    type = SilicaUiElementType.control

    def __init__(self, field_name, field_prefix=None, scope=None, form=None, **kwargs):
        super().__init__(**kwargs)
        self.field_name = field_name
        self.field_prefix = field_prefix
        self.form = form
        if not scope:
            self.set_scope(prefix=field_prefix)
        else:
            self.kwargs.update({'scope': scope})
        self.kwargs.update({
            'type': self.type,
            'field_name': field_name,
        })
        self.kwargs.update(kwargs)

    def set_scope(self, prefix=None):
        if prefix:
            scope = f'#/properties/{prefix}/properties/{self.field_name.lower()}'
        else:
            scope = f'#/properties/{self.field_name.lower()}'
        self.kwargs.update({'scope': scope})

    def get_ui_schema(self):
        field_config = self.form.get_field_config(self.field_name)
        if field_config:
            if field_config.rule:
                self.kwargs['rule'] = field_config.rule.get_rule_schema()
            self.kwargs.update(
                self._django_widget_to_ui_schema(self.form.fields[self.field_name], field_config=field_config)
            )
        else:
            self.kwargs.update(self._django_widget_to_ui_schema(self.form.fields[self.field_name]))
        return self.kwargs


class SilicaLayout(SilicaUiElement):
    elements = None
    # because layouts are not named and therefore do not have a SilicaFieldConfig, css_classes and rule must be manually
    # set
    rule = None
    css_classes = None

    def __init__(self, *args, rule=None, css_classes=None, **kwargs):
        super().__init__(**kwargs)
        self.rule = rule
        self.css_classes = css_classes
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

    def get_ui_schema(self):
        schema = self.kwargs
        # flatten elements
        schema['elements'] = [element.get_ui_schema() for element in self.elements]
        if self.css_classes:
            schema['options'] = {'overrideCss': self.css_classes}
        if self.rule:
            schema['rule'] = self.rule.get_rule_schema()
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

    def get_ui_schema(self):
        if any([e.type != SilicaUiElementType.category for e in self.elements]):
            raise Exception("Categorization elements may not have any non-Category direct children.")
        return super().get_ui_schema()


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

    def get_mapped_content(self, context):
        """ returns a dictionary of this element's generated id to the content it should render """
        return {self._id: template_from_string(self.content).render(context)}

    def get_ui_schema(self):
        schema = self.kwargs
        if self.rule:
            schema['rule'] = self.rule.get_rule_schema()
        return schema
