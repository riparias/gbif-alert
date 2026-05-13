"""Per-deployment Python overrides for the Docker compose stack.

This file is bind-mounted into the container at
/app/djangoproject/local_settings.py and imported at the END of settings.py.
Values defined here override env-driven defaults.

Most settings come from environment variables - see .env.example. Only
add things here that:

    1. Cannot be expressed as an env var (callables like PREDICATE_BUILDER).
    2. You explicitly prefer to keep in code rather than env.

If you set everything via env vars, this file can stay empty - but it
MUST exist next to docker-compose.yml because the compose file
unconditionally bind-mounts it.

Reference example for a custom GBIF download predicate (uncomment and edit
if the env-driven default builder is not flexible enough):

# from django.conf import settings
#
# def build_gbif_download_predicate(species_list):
#     return {
#         "predicate": {
#             "type": "and",
#             "predicates": [
#                 {"type": "equals", "key": "COUNTRY", "value": "BE"},
#                 {
#                     "type": "in",
#                     "key": "TAXON_KEY",
#                     "values": [str(s.gbif_taxon_key) for s in species_list],
#                 },
#                 {"type": "equals", "key": "OCCURRENCE_STATUS", "value": "present"},
#                 {"type": "greaterThanOrEquals", "key": "YEAR", "value": 2000},
#             ],
#         }
#     }
#
# settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"]["PREDICATE_BUILDER"] = (
#     build_gbif_download_predicate
# )
"""
