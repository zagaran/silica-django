from collections import defaultdict

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction


class SilicaSubFormField(forms.Field):
    """
        Implements a special field where the item is an object related to the form instance.

        To customize the behavior of this field, subclass it and implement your own handler functions as needed.

    """

    instance_form = None
    identifier_field = 'pk'
    parent_instance = None
    instance = None
    errors = []
    _raw = None
    _instantiated_form = None
    _prefixes_by_field = None

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance_form:
            raise NotImplementedError("You must define instance_form to use this field")
        if not issubclass(self.instance_form, forms.models.ModelForm):
            raise TypeError("instance_form must subclass ModelForm")
        if instance:
            self.instance = instance

    def get_instance(self):
        raise NotImplementedError("You must define get_instance to use this field")

    def refresh_data(self):
        if self.instance:
            self.instance.refresh_from_db()
        else:
            self.instance = self.get_instance()
        # force reinstantiation of form
        self._instantiated_form = None
        self.initial = self.instantiated_form.get_data_for_template()

    @property
    def instantiated_form(self):
        if not self._instantiated_form:
            if self.instance:
                self._instantiated_form = self.instance_form(instance=self.instance)
            else:
                self._instantiated_form = self.instance_form()
        return self._instantiated_form

    def get_sub_fields(self):
        return self.instantiated_form.fields

    def get_form_data_schema(self):
        return self.instantiated_form.get_data_schema()

    def get_form_ui_schema(self, field_prefix=None):
        return self.instantiated_form.get_ui_schema(field_prefix=field_prefix)

    def _instantiate_form(self, data=None, instance=None):
        # local import required to prevent cyclical imports
        from silica_django.forms import SilicaFormMixin
        # if the form subclasses silica form, include parent_instance as a kwarg
        kwargs = {'data': data, 'instance': instance}
        if issubclass(self.instance_form, SilicaFormMixin):
            kwargs['parent_instance'] = self.parent_instance
        return self.instance_form(**kwargs)

    def prepare_for_commit(self, data):
        if data:
            if self.identifier_field in data.keys():
                return self.handle_update(data)
            return self.handle_create(data)
        return None

    def handle_update(self, data):
        if not self.instance:
            self.instance = self.instance_form.Meta.model.objects.get(pk=data[self.identifier_field])
        form = self._instantiate_form(data=data, instance=self.instance)
        if form.is_valid():
            form.save()
            self.instance.refresh_from_db()
            return self.instance
        else:
            self.errors.append(form.errors)
            return None

    def handle_create(self, data):
        form = self._instantiate_form(data)
        if form.is_valid():
            form.save()
            # TODO: verify that this will return the newly created instance
            return form.instance
        else:
            self.errors.append(form.errors)
            return None
    def validate_against_form(self, form_data, instance=None):
        """ Ensure that data being passed from frontend validates against form """
        form = self._instantiate_form(data=form_data, instance=instance)
        form.is_valid()
        return form

    def data_as_form(self, data):
        # transforms raw data into a form
        form = self.validate_against_form(data, instance=self.instance)
        return form

    def to_python(self, data):
        self._raw = data
        if data in self.empty_values:
            return None
        form = self.data_as_form(data)
        if form.errors:
            raise ValidationError(form.errors)
        form.save()
        return form.instance.id


class SilicaSubFormArrayField(forms.Field):
    """
        Implements a special kind of array field where the items are objects related to the form instance.

        This field does not behave like standard form fields, because its behavior is fundamentally different
        from that of a standard form field, which acts on a single instance.

        Array saves are done in a single transaction. Any object which already has a primary key field gets updated; 
        any object without a primary key field gets created. Any object in the queryset whose value is not present in
        the data gets deleted (this may change).

        To customize the behavior of this field, subclass it and implement your own handler functions as needed.

        TODO: support usage in non-model Forms

    """

    instance_form = None
    identifier_field = 'pk'
    queryset = None
    batch_size = 200
    min_instances = 0
    max_instances = None
    # this value must be set by the initialization of the form
    parent_instance = None

    _instantiated_forms = []
    # the list of update errors by pk of object
    _update_errors = defaultdict(list)
    # the list of errors for this field (database errors)
    _errors = []
    _qs_lookup = None
    _raw = None

    def __init__(self, *args, queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance_form:
            raise NotImplementedError("You must define instance_form to use this field")
        if not issubclass(self.instance_form, forms.models.ModelForm):
            raise TypeError("instance_form must subclass ModelForm")
        if queryset:
            self.queryset = queryset

    def get_form_data_schema(self):
        return self.instance_form().get_data_schema()

    def get_queryset(self):
        if self.queryset:
            # this should force a refresh of the queryset
            return self.queryset.all()
        else:
            return self.instance_form.Meta.model.objects.all()

    @property
    def qs_lookup(self):
        if not self._qs_lookup:
            self._qs_lookup = {getattr(item, self.identifier_field): item for item in self.get_queryset()}
        return self._qs_lookup

    def prepare_for_commit(self, data):
        updates = []
        creates = []
        if data:
            for idx, item in enumerate(data):
                # the identifier field will either be the empty string or the correct value for the object
                pk = item.pop(self.identifier_field, None)
                if pk:
                    # if the item already has a pk, we are updating
                    update = self.handle_update(pk, item, idx=idx)
                    if update:
                        updates.append(update)
                else:
                    # if the item does not have a pk, we are creating
                    create = self.handle_create(item, idx=idx)
                    if create:
                        creates.append(create)
        return creates, updates

    def handle_delete(self, data):
        items_to_delete = self.get_items_to_delete(data)
        self.perform_delete(items_to_delete)

    def get_items_to_delete(self, data):
        if not data:
            data = []
        key = self.identifier_field
        item_keys = [datum[key] for datum in data if key in datum]
        return self.queryset.exclude(**{f'{key}__in': item_keys})

    def perform_delete(self, qs):
        """
        Actually performs the deletion operation on the queryset returned by handle_delete

        Args:
            qs: the queryset to be deleted
        """
        # add flag to turn off atomic operations (what to do for partial failures)
        # CRUD operations should be atomic with parent form
        try:
            qs.delete()
        except Exception as e:
            self._errors.append(f"There was an error deleting items. {repr(e)}")

    def prepare_create(self, item, idx=None):
        """

        Args:
            item: a dictionary representing the keys and values from the submitted form
        Keyword Args:
            idx: an integer representing the index of this item in the array (0-indexed)

        Returns:
            A Django Model object which can be passed to bulk_create
        """
        return self.queryset.model(item)

    def handle_create(self, item, idx=None):
        form = self.validate_against_form(item)
        if not form.errors:
            return self.prepare_create(form.cleaned_data, idx=idx)
        else:
            self._errors.append(f"There was an error creating an item. {form.errors}")
            return None

    def prepare_update(self, pk, item, idx=None):
        """

        Args:
            pk: the primary key of the object to be updated
            item: a dictionary representing the keys and values from the submitted form

        Keyword Args:
            idx: an integer representing the index of this item in the array (0-indexed)

        Returns:
            A Django Model object which can be passed to bulk_update
        """
        return self.queryset.model(item, **{self.identifier_field: pk})

    def handle_update(self, pk, item, idx=None):
        """

        Args:
            pk: the primary key of the object to be updated
            item: a dictionary representing the keys and values from the submitted form

        Keyword Args:
            idx: an integer representing the index of this item in the array (0-indexed)

        Returns:
            A Django Model object which can be passed to bulk_update or None if form errored
        """
        instance = self.qs_lookup[pk]
        form = self.validate_against_form(item, instance=instance)
        if not form.errors:
            return self.prepare_update(pk, form.cleaned_data, idx=idx)
        else:
            self._update_errors[pk].append(form.errors)
            return None

    def _instantiate_form(self, data=None, instance=None):
        # local import required to prevent cyclical imports
        from silica_django.forms import SilicaFormMixin
        # if the form subclasses silica form, include parent_instance as a kwarg
        kwargs = {'data': data, 'instance': instance}
        if issubclass(self.instance_form, SilicaFormMixin):
            kwargs['parent_instance'] = self.parent_instance
        return self.instance_form(**kwargs)

    def refresh_data(self):
        self.queryset = self.get_queryset()
        self._instantiated_forms = [self._instantiate_form(instance=instance) for instance in self.queryset]
        self.initial = [{**form.initial, f'{self.identifier_field}': getattr(form.instance, self.identifier_field)}
                        for form in self._instantiated_forms]

    def validate_against_form(self, form_data, instance=None):
        """ Ensure that data being passed from frontend validates against form """
        form = self._instantiate_form(data=form_data, instance=instance)
        form.is_valid()
        return form

    def validate(self, value):
        # runs after to_python, takes a value after coercion and raises validate error on any error, does not return anything
        super().validate(value)
        if value:
            errors = []
            for form in value:
                if form.errors:
                    errors.append(ValidationError(form.errors))
            if self._errors:
                errors.append(ValidationError([ValidationError(err) for err in self._errors]))
            if errors:
                raise ValidationError(errors)

    def data_as_forms(self, data):
        # transforms raw data into a list of forms
        forms = []
        for item in data:
            # the identifier field will either be the empty string or the correct value for the object
            pk = item.pop(self.identifier_field, None)
            instance = None
            if pk:
                instance = self.qs_lookup[pk]
            form = self.validate_against_form(item, instance=instance)
            forms.append(form)
        return forms

    def do_save(self):
        data = self._raw
        self.refresh_data()
        with transaction.atomic():
            # handle deletes
            self.handle_delete(data)
            creates, updates = self.prepare_for_commit(data)
            if creates:
                try:
                    self.queryset.model.objects.bulk_create(creates, batch_size=self.batch_size)
                except Exception as e:
                    self._errors.append(f"There was an error creating new objects. {repr(e)}")
            if updates:
                try:
                    self.queryset.model.objects.bulk_update(updates, self.instance_form._meta.fields,
                                                            batch_size=self.batch_size)
                except Exception as e:
                    self._errors.append(f"There was an error updating existing objects. {repr(e)}")
        # force form to re-do queryset and re-calculate initial values so that newly created & updated data is displayed on refresh
        self.refresh_data()

    def to_python(self, data):
        self._raw = data
        if data in self.empty_values:
            return None
        return self.data_as_forms(data)
