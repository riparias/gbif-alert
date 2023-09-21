# Current (unreleased)

- Users can now upload their owns areas of interest!
- Fixed an old display/linking bug (https://github.com/riparias/gbif-alert/issues/244)
- Vernacular name of species is now shown on the occurrence details page (https://github.com/riparias/gbif-alert/issues/262)
- Scientific name of species is now shown on the map popup (https://github.com/riparias/gbif-alert/issues/263)

# v1.4.1 (2023-09-18)   

- New data import script (specific to the LIFE RIPARIAS instance)

# v1.4.0 (2023-09-13)

- Experimental: a WFS server (returning all observations) is now available at `/api/wfs/observations`
- The histogram / bar chart now shows the full temporal range of data (instead of the last 5 years)
- Improved import script again to avoid crashes due to high memory usage

# v1.3.2 (2023-09-12)

- Improve import performances

# v1.3.1 (2023-09-07)

- Warning message instead of histogram when all values are 0, to avoid confusing display behaviour: https://github.com/riparias/gbif-alert/issues/92
- Fix a minor, recently introduced display issue: https://github.com/riparias/gbif-alert/issues/255
- Unused datasets are automatically cleaned up at import time: https://github.com/riparias/gbif-alert/issues/222
- Better synchronization of the Dataset name with GBIF: https://github.com/riparias/gbif-alert/issues/183
- More user-friendly language settings (https://github.com/riparias/gbif-alert/issues/257)

# v1.3.0 (2023-08-30)

- Users can now easily change their password
- The vernacular name is now shown in the observations table
- Improved "initial data import" filter/selector, according to the suggestions in https://github.com/riparias/gbif-alert/issues/251
- Internal improvement to improve the tool re-usability (https://github.com/riparias/gbif-alert/issues/250)
- Update dependencies

# v1.2.1 (2023-08-21)

- Fixed a display issue with the user menu in the navbar (https://github.com/riparias/gbif-alert/issues/252)

# v1.2.0  (2023-07-31)

- The GBIF download is now fully configurable, so instances are not limited to a single country
and can use any search predicate (see https://www.gbif.org/developer/occurrence#predicates)
- Improved installation instructions, including the template for the `local_settings_docker.py` file
- Added python-dotenv to the requirements so settings secrets can be configured via .env files

# v1.1.2  (2023-07-25)

- Minor changes to the Docker Compose setup

# v1.1.1  (2023-07-24)

- Minor changes to the Docker Compose setup

# v1.1.0  (2023-07-20)

- The project was renamed from `pterois` to `gbif-alert`
- Infrastructure: we now provide a Docker / Docker Compose setup for easier deployment
- Minor: A proper git tag name is shown as the version number in footer (if available, otherwise the commit hash is used as it was before)
- Minor: Better response if a user tries to see the details of someone else's alert (https://github.com/riparias/gbif-alert/issues/223)


# v1.0.0  (2023-07-12)

- First release as a reusable engine
