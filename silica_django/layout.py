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

    def __init__(self, **kwargs):
        if self.kwargs is None:
            self.kwargs = {
                **kwargs
            }


class Control(SilicaUiElement):
    type = SilicaUiElementType.control

    def __init__(self, field_name, scope=None, **kwargs):
        super().__init__(**kwargs)
        if scope is None:
            scope = f'#/properties/{field_name.lower()}'
        self.kwargs.update({
            'scope': scope,
            'type': self.type,
            'field_name': field_name,
        })
        self.kwargs.update(kwargs)

    def get_schema(self, rules):
        if self.kwargs['field_name'] in rules:
            self.kwargs['rule'] = rules[self.kwargs['field_name']].get_schema()
        return self.kwargs


class Controls:
    # wrapper class for multiple Controls
    elements = None

    def __init__(self, *args):
        """ arg may be either a single string or a dictionary of {label, **kwargs} """
        self.elements = []
        for arg in args:
            if isinstance(arg, str):
                self.elements.append(Control(arg))
            elif isinstance(arg, dict):
                self.elements.append(Control(arg['label'], **arg))
            else:
                raise Exception("Unsupported Element configuration; you must pass either a string or a dictionary")

    def get_schema(self, rules):
        return [e.get_schema(rules) for e in self.elements]


class SilicaLayout(SilicaUiElement):
    elements = None

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.elements = args
        self.kwargs.update({'type': self.type})

    def get_schema(self, rules):
        schema = self.kwargs
        # flatten elements
        elements = list(map(lambda e: e.get_schema(rules), self.elements))
        final_elements = []
        for e in elements:
            if isinstance(e, list):
                for i in e:
                    final_elements.append(i)
            else:
                final_elements.append(e)
        schema['elements'] = final_elements
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

    def get_schema(self, rules):
        if any([e.type != SilicaUiElementType.category for e in self.elements]):
            raise Exception("Categorization elements may not have any non-Category direct children.")
        return super().get_schema(rules)


class Category(SilicaLayout):
    type = SilicaUiElementType.category
    label = None

    def __init__(self, label, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kwargs.update({'label': label})
