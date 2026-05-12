"""Optional per-deployment overrides for the manual (non-Docker) deploy.

Most settings now come from environment variables - see `.env.example`
at the project root for the full list. Only put things in this file that
either:

    1. Cannot be expressed as an env var (callables like
       `PREDICATE_BUILDER`).
    2. You explicitly prefer to keep in code rather than env.

How to use this template
------------------------
Copy this file to `local_settings.py` (sibling, gitignored) only if you
need an escape hatch. If you set everything via env vars, you do NOT
need to create `local_settings.py` at all - `settings.py` is
self-sufficient and validates required values at the end of its module
body.

How loading works
-----------------
`djangoproject/settings.py` imports `djangoproject.local_settings`
(this file's runtime sibling) AFTER all env-driven settings have been
read, so any setting defined here overrides the env-driven default.

Example: a custom GBIF download predicate
-----------------------------------------
Uncomment and edit the block below if the env-driven default builder
(`GBIF_DOWNLOAD_COUNTRY` + `GBIF_DOWNLOAD_YEAR_MIN`) is not flexible
enough for your deployment.
"""

# from django.conf import settings
#
#
# def build_gbif_download_predicate(species_list):
#     """Custom predicate. `species_list` is a `QuerySet[Species]`."""
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
#
# settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"]["PREDICATE_BUILDER"] = (
#     build_gbif_download_predicate
# )
