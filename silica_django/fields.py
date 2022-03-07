"""

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

    def __init__(self, *args, identifier_field='pk', batch_size=200, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance_form:
            raise NotImplementedError("You must define instance_form to use this field")
        if not isinstance(self.instance_form, forms.models.ModelFormMetaclass):
            # TODO: figure out why we can't just check for forms.ModelForm and document the reason
            raise TypeError(f"instance_form must be a model form, not {type(self.instance_form)}")
        self.instantiated_forms = []
        self.identifier_field = identifier_field
        # this value must be set by the initialization of the form
        self.parent_instance = None
        self._queryset = None
        self.batch_size = batch_size
        # the list of update errors by pk of object
        self.update_errors = defaultdict(list)
        # the list of errors for this field (database errors)
        self.errors = []

    def get_queryset(self):
        return self.instance_form._meta.model.objects.all()

    @property
    def qs_lookup(self):
        return {item[self.identifier_field]: item for item in self.queryset}

    def get_items_to_delete(self, data):
        key = self.identifier_field
        item_keys = [datum[key] for datum in data if datum[key]]
        return self.queryset.exclude(**{f'{key}__in': item_keys})

    def process_data(self, data):
        items_to_delete = self.get_items_to_delete(data)
        self.handle_delete(items_to_delete)
        updates = []
        creates = []
        for item in data:
            # the identifier field will either be the empty string or the correct value for the object
            pk = item[self.identifier_field]
            if pk:
                # if the item already has a pk, we are updating
                update = self.handle_update(pk, item)
                if update:
                    updates.append(update)
            else:
                # if the item does not have a pk, we are creating
                create = self.do_create(item)
                if create:
                    creates.append(create)
        return creates, updates

    def handle_delete(self, qs):
        try:
            qs.delete()
        except Exception as e:
            self.errors.append(f"There was an error deleting items. {repr(e)}")

    def clean_data_for_create(self, item):
        # pk has default value of "" since the field must exist in the form; if it exists, clear it
        del item[self.identifier_field]
        return item

    def do_create(self, item):
        item = self.clean_data_for_create(item)
        return self.handle_create(item)

    def handle_create(self, item):
        cleaned_data, errors = self.validate_against_form(item)
        if not errors:
            new_item = self.queryset.model(**cleaned_data)
            return new_item
        else:
            self.errors.append(f"There was an error creating an item. {errors}")
            return None

    def handle_update(self, pk, item):
        print('updating')
        instance = self.qs_lookup[pk]
        cleaned_data, errors = self.validate_against_form(item, instance=instance)
        if not errors:
            return self.queryset.model(**cleaned_data, **{self.identifier_field: pk})
        else:
            self.update_errors[pk].append(errors)
            return None

    @property
    def queryset(self):
        if self._queryset is None:
            self.refresh_data()
        return self._queryset

    def refresh_data(self):
        self._queryset = self.get_queryset()
        self.instantiated_forms = [self.instance_form(instance=instance) for instance in self._queryset]
        self.initial = [{**form.initial, f'{self.identifier_field}': getattr(form.instance, self.identifier_field)}
                        for form in self.instantiated_forms]

    def validate_against_form(self, form_data, instance=None):
        """ Ensure that data being passed from frontend validates against form """
        form = self.instance_form(form_data, instance=instance)
        form.is_valid()
        return form.cleaned_data, form.errors

    def to_python(self, data):
        print('to_python')
        # TODO: verify when this is called so we're not duplicating work
        if data in self.empty_values:
            return None
        # set up queryset outside atomic transaction
        self.refresh_data()
        with transaction.atomic():
            creates, updates = self.process_data(data)
            print("creates", creates)
            print("updates", updates)
            try:
                self.queryset.model.objects.bulk_create(creates, batch_size=self.batch_size)
            except Exception as e:
                self.errors.append(f"There was an error creating new objects. {repr(e)}")
            try:
                self.queryset.model.objects.bulk_update(updates, self.instance_form._meta.fields, batch_size=self.batch_size)
            except Exception as e:
                self.errors.append(f"There was an error updating existing objects. {repr(e)}")
        # force form to re-do queryset and re-calculate initial values so that newly created & updated data is displayed on refresh
        self._queryset = None
        print(self.errors)
        return data
