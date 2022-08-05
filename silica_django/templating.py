from django.template import engines
from django.template.exceptions import TemplateSyntaxError, TemplateDoesNotExist


def template_from_string(template_string, using=None):
    """
    Convert a string into a template object,
    using a given template engine or using the default backends 
    from settings.TEMPLATES if no engine was specified.

    Adapted from https://stackoverflow.com/questions/2167269/load-template-from-a-string-instead-of-from-a-file
    """
    # This function is based on django.template.loader.get_template, 
    # but uses Engine.from_string instead of Engine.get_template.
    chain = []
    engine_list = engines.all() if using is None else [engines[using]]
    for engine in engine_list:
        try:
            return engine.from_string(template_string)
        except TemplateSyntaxError as e:
            chain.append(e)
    raise TemplateDoesNotExist(template_string, chain=chain)
