# GBIF Alert

<!-- badges: start -->
[![Django CI](https://github.com/riparias/gbif-alert/actions/workflows/django_tests.yml/badge.svg)](https://github.com/riparias/gbif-alert/actions/workflows/django_tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
<!-- badges: end -->

GBIF Alert is a [GBIF](https://www.gbif.org)-based early alert system for invasive species.

Visit the project website at [www.gbif-alert.org](https://www.gbif-alert.org) for an overview, or try the [official demo instance](https://demo.gbif-alert.org).

## News

- **GBIF Alert 2.0 is here!** A major release: a brand-new single-page UI, new
  proximity filtering (observations inside or *approaching* your areas), a modern
  public API (v2), and a fully reworked Docker/deployment stack. See the
  [changelog](CHANGELOG.md).

It is a reusable website engine powered by [Django](https://www.djangoproject.com/) available under the [MIT license](LICENSE).
Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.

## Getting started

GBIF Alert allows you to monitor a list of species, and be notified of new occurrences on GBIF via email.

Multiple websites using GBIF alert (called *instances*) exists, in order to target different communities:

- **You are an end-user that just want to be informed of new occurrence in the GBIF network?** Join [an existing instance](#user-content-gbif-alert-instances-in-the-wild) that covers your area and species of interest, register and start configuring your alerts! Here is a demonstration video: https://www.youtube.com/watch?v=bixaTGRIZ4A

- **You have more technical knowledge and want to install your own instance of GBIF Alert?** No problem: GBIF Alert is fully configurable, and we provide facilities to make it easy to install and deploy. 
See [INSTALL.md](INSTALL.md) for more information.

## GBIF Alert instances in the wild

- LIFE RIPARIAS Early Alert: [production](https://alert.riparias.be) / [development](https://dev-alert.riparias.be) (Targets riparian invasive species in Belgium)
- [GBIF Alert demo instance](https://demo.gbif-alert.org) (Always in sync with the `devel` branch of this repository)
- The Belgian Biodiversity Platform uses GBIF alert under the hood as an API for the ManaIAS project. 

## API

GBIF Alert exposes a stable, supported public HTTP API (API v2) for programmatic access to its data.

Each instance documents its own API: visit `/api-docs` on any instance for an overview, with the interactive reference at `/api/v2/docs` and an OGC WFS service at `/api/wfs/observations/`. For example, on the demo instance: https://demo.gbif-alert.org/api-docs

The older `/api/*` JSON endpoints are deprecated in favour of API v2 and will be removed on 30 June 2027.

## Funding and acknowledgements

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="static_global/eu-funding/eu-funded-en-negative.png">
  <img src="static_global/eu-funding/eu-funded-en.png" alt="Funded by the European Union" width="280">
</picture>

Development of GBIF Alert has been supported by the European Union's Horizon Europe research and
innovation programme under grant agreements No 101181413 (GuardIAS) and No 101180559 (OneSTOP),
and previously by LIFE RIPARIAS.

Funded by the European Union. Views and opinions expressed are however those of the author(s)
only and do not necessarily reflect those of the European Union or the European Research
Executive Agency (REA). Neither the European Union nor the granting authority can be held
responsible for them.

GBIF Alert was also awarded the first prize of the [GBIF Ebbe Nielsen Challenge 2023](https://www.gbif.org/fr/news/EQgUzZ4YA75BSeLs1naI9/).

The EU emblem above acknowledges the funding of **this software**. It is *not* shown to end users
by default: a running instance displays it only if its operator explicitly opts in, which only
genuinely EU-funded instances may do. See [docs/eu-funding-acknowledgement.md](docs/eu-funding-acknowledgement.md).
