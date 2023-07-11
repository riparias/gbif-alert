# Pterois

<!-- badges: start -->
[![Django CI](https://github.com/riparias/pterois/actions/workflows/django_tests.yml/badge.svg)](https://github.com/riparias/early-alert-webapp/actions/workflows/django_tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Automatic deployment - demo server](https://github.com/riparias/pterois/actions/workflows/deploy_demo.yml/badge.svg?branch=devel)](https://github.com/riparias/pterois/actions/workflows/deploy_demo.yml)
<!-- badges: end -->

Pterois is a [GBIF](https://www.gbif.org)-based early alert system for invasive species.

In practice:

- It is a reusable and open-source (MIT licence) Django-based website
- That can be configured to monitor a list of species in a given area of interest
- ... and be deployed on a server at a given URL => we'd call that a *Pterois instance*
- This instance will automatically download GBIF data for the species in the area of interest at a given frequency (typically daily)
- Finally, users / visitors of the instance can see the latest GBIF data for the species in the area of interest, and be notified of new occurrences via email

Developer documentation is available in [CONTRIBUTING.md](CONTRIBUTING.md).

## How to install a Pterois instance

See [INSTALL.md](INSTALL.md).

## Pterois instances in the wild

- [LIFE RIPARIAS Early Alert](https://alert.riparias.be) (Targets riparian invasive species in Belgium)
- [Pterois demo instance](https://pterois-demo.niconoe.eu/) (Always in sync with the `devel` branch of this repository)