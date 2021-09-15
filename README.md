# LIFE RIPARIAS early alert web application

<!-- badges: start -->
[![Django CI](https://github.com/riparias/early-warning-webapp/actions/workflows/django_tests.yml/badge.svg)](https://github.com/riparias/early-warning-webapp/actions/workflows/django_tests.yml)
[![Funding](https://img.shields.io/static/v1?label=powered+by&message=LIFE+RIPARIAS&labelColor=323232&color=00a58d)](https://www.riparias.be/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
<!-- badges: end -->

This repository contains the source code of the early warning web application for [LIFE RIPARIAS](https://www.riparias.be/) (Action A.1.2).

Early prototype visible on the development server http://54.75.164.69/

## Development setup and notes

### Backbone
- [Python](https://www.python.org/) 3.8, [(Geo)Django](https://www.djangoproject.com/) 3.2 LTS, [PostgreSQL](https://www.postgresql.org/), [PostGIS](https://postgis.net/) 3.1+, [TypeScript](https://www.typescriptlang.org/) and [Vue.js](https://vuejs.org/)
- CSS: [Bootstrap](https://getbootstrap.com/) 5.1  
- [Poetry](https://python-poetry.org/) to manage dependencies (use `poetry add`, `poetry install`, ... instead of pip). PyCharm also has a Poetry plugin available.

### Dev environment
- Python>=3.8, PostGIS>=3.1 and npm are required
- copy `local_settings.template.py` to `local_settings.py`, adjust those settings and point Django to `local_settings.py`
- point Django to `local_settings`

### CI-CD

We make use of GitHub Actions when possible.

They're currently used to:
- Run Django tests and `mypy` on push
- Deploy to dev server on push

### Frontend-backend integration

We use a hybrid approach such as described in https://www.saaspegasus.com/guides/modern-javascript-for-django-developers/integrating-javascript-pipeline/:

- npm is used to manage JS dependencies (**npm install** should be run)
- **During development**, run `npm run webpack-dev` so Webpack constantly watches our source frontend (in `./assets`) and create bundles (in `./static`)
- **When deploying**, use `npm run webpack prod` instead (smaller bundle size + one single copy - rather than watching files)

### Code formatting

We use `black` (for Python code) and `prettier` (for JS/TS/Vue) to automatically and consistently format the source code.
Contributors: please configure your favorite editor/IDE to format on save. 

### Data import mechanism

The data shown in the webapp can be automatically updated by running the `import_occurrences` management command. 
This one will trigger a GBIF Download for our search of interest (target country + species in the database) and 
load the corresponding occurrences into the database. At the end of the process, occurrences from previous data 
imports are deleted.

The data import history is recorded with the DataImport model, and shown to the user on the "about" page.

=> For a given occurrence, Django-managed IDs are therefore not stable, but the GBIF ids fortunately are.