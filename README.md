# early-warning-webapp
Source code of the early warning web application for Riparias

## Development setup and notes

- Backbone: Python 3.8, (Geo)Django 3.2 LTS, PostgreSQL, PostGIS 3.1+
- Experiment: we use [Poetry](https://python-poetry.org/) to manage dependencies (use `poetry add`, `poetry install`, ... instead of pip). PyCharm also has a Poetry plugin available.
- copy `local_settings.template.py` to `local_settings.py`, adjust those settings and point Django to `local_settings.py`
