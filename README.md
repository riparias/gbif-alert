# LIFE RIPARIAS early alert web application

<!-- badges: start -->
[![Django CI](https://github.com/riparias/early-alert-webapp/actions/workflows/django_tests.yml/badge.svg)](https://github.com/riparias/early-alert-webapp/actions/workflows/django_tests.yml)
[![Funding](https://img.shields.io/static/v1?label=powered+by&message=LIFE+RIPARIAS&labelColor=323232&color=00a58d)](https://www.riparias.be/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Deployment on dev server](https://github.com/riparias/early-alert-webapp/actions/workflows/deploy_dev_server.yml/badge.svg)](https://github.com/riparias/early-alert-webapp/actions/workflows/deploy_dev_server.yml)
<!-- badges: end -->

This repository contains the source code of the early alert web application for [LIFE RIPARIAS](https://www.riparias.be/) (Action A.1.2).

Development version visible on [dev-alert.riparias.be](http://dev-alert.riparias.be/).

Developer documentation is available in [CONTRIBUTING.md](CONTRIBUTING.md).

## Next steps

See [open issues](https://github.com/riparias/early-alert-webapp/issues) and [milestones](https://github.com/riparias/early-alert-webapp/milestones).


TODO:

- My area page:
  - Better styling
  - Add specific instructions for file requirements. minimal:
    - geopackage / shapefile / geojson?
    - EPSG data present (tested with 4326, 3857 and Lambert 72)
    - 1 single polygon or a multipolygon?
  - Add tests... 

- Write a test to make sure areas and species must be explicitly selected when creating an alert