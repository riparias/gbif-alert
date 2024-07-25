# GBIF Alert

<!-- badges: start -->
[![Django CI](https://github.com/riparias/gbif-alert/actions/workflows/django_tests.yml/badge.svg)](https://github.com/riparias/gbif-alert/actions/workflows/django_tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Automatic deployment - demo server](https://github.com/riparias/gbif-alert/actions/workflows/deploy_demo.yml/badge.svg?branch=devel)](https://github.com/riparias/gbif-alert/actions/workflows/deploy_demo.yml)
<!-- badges: end -->

GBIF Alert is a [GBIF](https://www.gbif.org)-based early alert system for invasive species.

🎉 **GBIF Alert has been awarded the first prize of the [GBIF Ebbe Nielsen Challenge 2023](https://www.gbif.org/fr/news/EQgUzZ4YA75BSeLs1naI9/)!** 🎉 

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
- [GBIF Alert demo instance](https://gbif-alert-demo.thebinaryforest.net/) (Always in sync with the `devel` branch of this repository)
- The Belgian Biodiversity Platform uses GBIF alert under the hood as an API for the ManaIAS project. 