# early-warning-webapp

<!-- badges: start -->
[![Django CI](https://github.com/riparias/early-warning-webapp/actions/workflows/django_tests.yml/badge.svg)](https://github.com/riparias/early-warning-webapp/actions/workflows/django_tests.yml)
[![Funding](https://img.shields.io/static/v1?label=powered+by&message=LIFE+RIPARIAS&labelColor=323232&color=00a58d)](https://www.riparias.be/)
<!-- badges: end -->

Source code of the early warning web application for [LIFE RIPARIAS](https://www.riparias.be/) (Action A.1.2).

Early prototype visible at http://54.75.164.69/

## Development setup and notes

- Backbone: Python 3.8, (Geo)Django 3.2 LTS, PostgreSQL, PostGIS 3.1+, Vue.js
- CSS: Bootstrap 5.1  
- Experiment: we use [Poetry](https://python-poetry.org/) to manage dependencies (use `poetry add`, `poetry install`, ... instead of pip). PyCharm also has a Poetry plugin available.
- copy `local_settings.template.py` to `local_settings.py`, adjust those settings and point Django to `local_settings.py`

### Frontend-backend integration

We use a hybrid approach such as described in https://www.saaspegasus.com/guides/modern-javascript-for-django-developers/integrating-javascript-pipeline/.

In short:

- We use npm to manage JS dependencies
- Run `npm run webpack-dev` so Webpack constantly watches our source frontend (in `./assets`) and create bundles (in `./static`)
- When deploying, use `npm run webpack prod` instead (smaller bundle size + one single copy - rather than watching files)

### Code formatting

- Use `black` for Python code
- Use `prettier` to reformat JS/TS/Vue code (see [PyCharm configuration instructions](https://www.jetbrains.com/help/pycharm/prettier.html))
