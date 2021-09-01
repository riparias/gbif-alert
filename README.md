# early-warning-webapp

[![Django CI](https://github.com/riparias/early-warning-webapp/actions/workflows/django_tests.yml/badge.svg)](https://github.com/riparias/early-warning-webapp/actions/workflows/django_tests.yml)

Source code of the early warning web application for Riparias

## Development setup and notes

- Backbone: Python 3.8, (Geo)Django 3.2 LTS, PostgreSQL, PostGIS 3.1+, Vue.js
- CSS: Bootstrap 5.1  
- Experiment: we use [Poetry](https://python-poetry.org/) to manage dependencies (use `poetry add`, `poetry install`, ... instead of pip). PyCharm also has a Poetry plugin available.
- copy `local_settings.template.py` to `local_settings.py`, adjust those settings and point Django to `local_settings.py`

### Frontend-backend integration

We use a hybrid approach such as described in https://www.saaspegasus.com/guides/modern-javascript-for-django-developers/integrating-javascript-pipeline/.

In short

- We use npm to manage JS dependencies
- Run `npm run dev` so Webpack watches our source frontend (in `./assets`) and create bundles (in `./static`)