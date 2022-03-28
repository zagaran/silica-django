from collections import defaultdict

from django import forms
from django.db import transaction


class SilicaModelFormArrayField(forms.Field):
    """
        Implements a special kind of array field where the items are objects related to the form instance.

        This field does not behave like standard form fields, because its behavior is fundamentally different
        from that of a standard form field, which acts on a single instance.

        Array saves are done in a single transaction. Any object which already has a primary key field gets updated; 
        any object without a primary key field gets created. Any object in the queryset whose value is not present in
        the data gets deleted (this may change).

        To customize the behavior of this field, subclass it and implement your own handler functions as needed.

    """

    instance_form = None
    identifier_field = 'pk'
    queryset = None
    batch_size = 200
    # this value must be set by the initialization of the form
    parent_instance = None

    _instantiated_forms = []
    # the list of update errors by pk of object
    _update_errors = defaultdict(list)
    # the list of errors for this field (database errors)
    _errors = []
    _qs_lookup = None

    def __init__(self, *args, queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance_form:
            raise NotImplementedError("You must define instance_form to use this field")
        if not isinstance(self.instance_form, forms.models.ModelFormMetaclass):
            # TODO: figure out why we can't just check for forms.ModelForm and document the reason
            raise TypeError(f"instance_form must be a model form, not {type(self.instance_form)}")
        if queryset:
            self.queryset = queryset

    def get_queryset(self):
        if self.queryset:
            # this should force a refresh of the queryset
            return self.queryset.all()
        else:
            return self.instance_form._meta.model.objects.all()

    @property
    def qs_lookup(self):
        if not self._qs_lookup:
            self._qs_lookup = {item[self.identifier_field]: item for item in self.queryset}
        return self._qs_lookup

    def process_data(self, data):
        updates = []
        creates = []
        for item in data:
            # the identifier field will either be the empty string or the correct value for the object
            pk = item.pop(self.identifier_field, None)
            if pk:
                # if the item already has a pk, we are updating
                update = self.handle_update(pk, self.clean_data(item))
                if update:
                    updates.append(update)
            else:
                # if the item does not have a pk, we are creating
                create = self.handle_create(self.clean_data(item))
                if create:
                    creates.append(create)
        return creates, updates

    def do_deletion(self, data):
        items_to_delete = self.get_items_to_delete(data)
        self.handle_delete(items_to_delete)

    def get_items_to_delete(self, data):
        if not data:
            data = []
        key = self.identifier_field
        item_keys = [datum[key] for datum in data if datum[key]]
        return self.queryset.exclude(**{f'{key}__in': item_keys})

    def clean_data(self, item):
        # by default, do nothing; exists so that we can hook into it as necessary. Note that this is called before 
        # both handle_create() and handle_update()
        return item

    def handle_delete(self, qs):
        try:
            qs.delete()
        except Exception as e:
            self._errors.append(f"There was an error deleting items. {repr(e)}")

    def handle_create(self, item):
        form = self.validate_against_form(item)
        if not form.errors:
            new_item = self.queryset.model(**form.cleaned_data)
            return new_item
        else:
            self._errors.append(f"There was an error creating an item. {form.errors}")
            return None

    def handle_update(self, pk, item):
        instance = self.qs_lookup[pk]
        form = self.validate_against_form(item, instance=instance)
        if not form.errors:
            return self.queryset.model(**form.cleaned_data, **{self.identifier_field: pk})
        else:
            self._update_errors[pk].append(form.errors)
            return None

    def refresh_data(self):
        self.queryset = self.get_queryset()
        self._instantiated_forms = [self.instance_form(instance=instance) for instance in self.queryset]
        self.initial = [{**form.initial, f'{self.identifier_field}': getattr(form.instance, self.identifier_field)}
                        for form in self._instantiated_forms]

    def validate_against_form(self, form_data, instance=None):
        """ Ensure that data being passed from frontend validates against form """
        form = self.instance_form(form_data, instance=instance)
        form.is_valid()
        return form

    def to_python(self, data):
        # TODO: verify when this is called so we're not duplicating work
        # set up queryset outside atomic transaction
        self.refresh_data()
        # handle deletes
        self.do_deletion(data)
        if data in self.empty_values:
            return None
        with transaction.atomic():
            creates, updates = self.process_data(data)
            try:
                self.queryset.model.objects.bulk_create(creates, batch_size=self.batch_size)
            except Exception as e:
                self._errors.append(f"There was an error creating new objects. {repr(e)}")
            try:
                self.queryset.model.objects.bulk_update(updates, self.instance_form._meta.fields, batch_size=self.batch_size)
            except Exception as e:
                self._errors.append(f"There was an error updating existing objects. {repr(e)}")
        # force form to re-do queryset and re-calculate initial values so that newly created & updated data is displayed on refresh
        self.refresh_data()
        return data
