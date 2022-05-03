# silica-django
A Django app which translates Django forms data into JSONSchema and UISchema as expected by the jsonforms frontend library.


## Installation
1. Install the library (`pip install silica-django`)
2. Add `"silica_django"` to your `INSTALLED_APPS`


## Sample Project
A sample project demonstrating simple usage of this library, using the companion frontend library [Silica for Vue](https://github.com/zagaran/silica-vue), can be found [here](https://github.com/zagaran/sample-silica-django-app).

## Tests
There is a (relatively sparse) test suite which comes with this library to prevent regression. To run it, simply run `python silica_django/tests.py` from the root directory.

## Documentation
There is a combined documentation repository for all Silica libraries located at [Silica-Docs](https://www.github.com/zagaran/silica-docs).