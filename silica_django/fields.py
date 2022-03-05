"""
array saves are done in a single transaction

- anything with an id gets updated
- anything without an id gets created
- ordering elements
- new elements
- specify primary key

    users = SilicaFormArrayField(UserEditForm, 
        lambda organization: User.objects.filter(user_info__organization=organization), 
        delete_override=lambda user: if user.id..., **kwargs)

"""
from collections import defaultdict

from django import forms
from django.db import transaction


class SilicaFormArrayField(forms.Field):
    """
        Implements a special kind of array field where the items are objects related to the form instance.

        This field does not behave like standard form fields, because its behavior is fundamentally different
        from that of a standard form field, which acts on a single instance.
    """

    def __init__(self, instance_form, queryset_fn, *args, delete_override=None, identifier_field='pk',
                 queryset_kwargs=None, batch_size=200, new_item_kwargs=None, create_function=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance_form = instance_form
        self.instantiated_forms = None
        self.queryset_fn = queryset_fn
        self.delete_override = delete_override
        self.identifier_field = identifier_field
        self.queryset_kwargs = queryset_kwargs or {}
        # this value must be set by the initialization of the form
        self.parent_instance = None
        self._queryset = None
        self.batch_size = batch_size
        self.new_item_kwargs = new_item_kwargs or {}
        self.create_function = create_function
        # the list of errors by pk of object
        self.errors_list = None
        # the list of errors for this field (database errors)
        self.non_field_errors_list = None

    @property
    def queryset(self):
        if self._queryset is None:
            self.refresh_data()
        return self._queryset

    def refresh_data(self, select_for_update=False):
        # TODO: is select_for_update necessary?
        self._queryset = self.queryset_fn(self.parent_instance, select_for_update=select_for_update, **self.queryset_kwargs)
        self.instantiated_forms = [self.instance_form(instance=instance) for instance in self._queryset]
        self.initial = [{**form.initial, f'{self.identifier_field}': getattr(form.instance, self.identifier_field)}
                        for form in self.instantiated_forms]

    def validate_against_form(self, instance, form_data):
        """ Ensure that data being passed from frontend validates against form """
        form = self.instance_form(form_data, instance=instance)
        form.is_valid()
        return form.cleaned_data, form.errors

    def to_python(self, data):
        if data in self.empty_values:
            return None
        errors_list = defaultdict(list)
        non_field_errors_list = []
        # set up queryset outside atomic transaction
        self.refresh_data(select_for_update=True)
        with transaction.atomic():
            # first, delete any item in the queryset which is no longer in the data set
            key = self.identifier_field
            item_keys = [datum[key] for datum in data if datum[key] != '']
            items_to_delete = self.queryset.exclude(**{f'{key}__in': item_keys})
            try:
                if not self.delete_override:
                    items_to_delete.delete()
                else:
                    self.delete_override(items_to_delete)
            except Exception:
                non_field_errors_list.append("There was an error removing existing items.")
            # TODO: handle de-duplication?
            updates = []
            creates = []
            for item in data:
                pk = item[key]
                if pk:
                    instance = self.queryset.get(**{key: pk})
                    cleaned_data, errors = self.validate_against_form(instance, item)
                    if not errors:
                        updates.append(self.queryset.model(**cleaned_data, **{key: pk}))
                    else:
                        errors_list[pk].append(errors)
                else:
                    # if there is no PK, we must be creating a new item
                    # create any new item; assume that all required fields are part of the form or provided in new_item_kwargs
                    del item[key]
                    if self.create_function:
                        creates.append(self.create_function(self.parent_instance, item, **self.new_item_kwargs))
                    else:
                        creates.append(self.queryset.model(**item))
            try:
                self.queryset.model.objects.bulk_create(creates, batch_size=self.batch_size)
            except Exception:
                non_field_errors_list.append("There was an error creating new objects.")
            try:
                self.queryset.model.objects.bulk_update(updates, self.instance_form._meta.fields, batch_size=self.batch_size)
            except Exception:
                non_field_errors_list.append("There was an error updating existing objects.")
        # force form to re-do queryset and initial values
        self._queryset = None
        self.non_field_errors_list = non_field_errors_list
        self.errors_list = errors_list
        return data
