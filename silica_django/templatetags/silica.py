from django import template

register = template.Library()


@register.inclusion_tag('silica_loader.html')
def load_silica_form(form, form_id):
    return {
        "form": form,
        "form_data_key": form_id + "-data",
        "form_schema_key": form_id + "-schema",
        "form_ui_schema_key": form_id + "-ui-schema",
        "form_errors_key": form_id + "-errors",
        "custom_elements_key": form_id + "-custom-elements",
    }
