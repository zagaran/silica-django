import random
import string

from silica_django.fields import SilicaSubFormField
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
    form = None
    rule = None
    config = None

    def __init__(self, *args, form=None, rule=None, config=None, **kwargs):
        if self.kwargs is None:
            self.kwargs = {
                **kwargs
            }
        self.form = form
        self.rule = rule
        self.config = config

    def set_form(self, form):
        # prevent overriding form if it is already set (subforms)
        if not self.form:
            self.form = form

    def get_ui_schema(self):
        raise NotImplemented

    def __repr__(self):
        return f"{self.type}: {self.field_name}"


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
        field = self.form.fields.get(self.field_name, None)
        if isinstance(field, SilicaSubFormField):
            subform_elements = field.instantiated_form.get_elements()
            return self.form.create_subform_container(field, subform_elements).get_ui_schema()
        field_config = self.config or self.form.get_field_config(self.field_name)
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
    # because layouts are not named and therefore do not have a SilicaFieldConfig, css_classes and rule must be manually
    # set
    css_classes = None
    form = None
    args = None

    def __init__(self, *args, css_classes=None, form=None, **kwargs):
        super().__init__(**kwargs)
        self.css_classes = css_classes
        # args should be a list of SilicaUiElements
        self.args = args
        self.kwargs.update({'type': self.type})
        self.form = form

    @property
    def elements(self):
        return [self._process_arg(a) for a in self.args]

    def _process_arg(self, arg):
        # if arg is a SilicaUiElement, we are recursing through a layout; if it is a string, we have to construct a Control
        if type(arg) == str:
            return Control(arg, form=self.form)
        elif isinstance(arg, SilicaUiElement):
            arg.set_form(self.form)
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
