# Development setup and notes

## Technological backbone
- [Python](https://www.python.org/) 3.11+, [(Geo)Django](https://www.djangoproject.com/) 4.2 [PostgreSQL](https://www.postgresql.org/), [PostGIS](https://postgis.net/) 3.1+, [Redis](https://redis.io/),  [TypeScript](https://www.typescriptlang.org/) and [Vue.js v3](https://vuejs.org/)
- CSS: [Bootstrap](https://getbootstrap.com/) 5.3  
- [Poetry](https://python-poetry.org/) is used to manage dependencies (use `poetry add`, `poetry install`, ... instead of pip). PyCharm also has a Poetry plugin available.

## Dev environment configuration
- Python>=3.11, PostGIS>=3.1, Redis and `npm` are required
- Use [Poetry](https://python-poetry.org/) to create an isolated virtualenv and install dependencies (`poetry install`) 
- Copy `local_settings.template.py` to `local_settings.py`, adjust those settings and point Django to `local_settings.py`
- [Point Django to local_settings](https://docs.djangoproject.com/en/3.2/topics/settings/#designating-the-settings)

## Testing / typing
This project provides the following tools to ensure the application and code stays in a decent state:

- Standard Django tests (can be run with `$ ./manage.py test`), including Selenium-based testing for frontend features and high-level tests
- Typing: can be checked with `$ mypy .`

Those should be run frequently on the developer's machines, but will also be executed by GitHub actions each time the code is pushed to GitHub (see the CI-CD section)

## CI-CD

We make use of GitHub Actions when possible. They're currently used to:

- Run Django tests and `mypy` on every push
- Automatically deploy the `devel` branches to the respective server when code is pushed (see `Working with 
  branches` below) 

## Working with branches

While deployment in production is currently manually run, it's crucial to keep it in an "always 
deployable" state and code should **never** be committed directly to the `main` branch.

The current workflow is:

1) New features and bug fixes are implemented in their own specific branches (created from `main`). 
2) After being checked locally and deemed satisfactory, the new branch is merged to `devel`
3) `devel` is pushed to GitHub: the updated version can be tested on the development server and shared with stakeholders.
4) after everything is confirmed ok, the `devel` branch is merged to `main`
5) `main` is pushed to GitHub
6) code is (currently) manually deployed in production via the `deploy_main.sh` script

For small, non-risky changes, steps 1-3 can be avoided by committing directly to the `devel` branch.

## Dependencies

We try to frequently update dependencies. Process is:

- Backend: `$ poetry update`
- Frontend: `$ npm-check -u`
- Run unit tests (+ a few manual checks?)
- Commit changes (should include `package.json`, `package-lock.json` and `poetry lock`)

## Database diagram

Last update: 01 aug 2023.
![tables diagram](./table-diagram.png)

## Frontend-backend integration

We use a hybrid approach such as described in https://www.saaspegasus.com/guides/modern-javascript-for-django-developers/integrating-javascript-pipeline/:

- npm is used to manage JS dependencies (**npm install** should be run once)
- **During development**, run `npm run webpack-dev` so Webpack constantly watches our source frontend (in `./assets`) and create bundles (in `./static`)
- **When deploying**, use `npm run webpack-prod` instead (smaller bundle size + one single copy - rather than watching files)

## Code formatting

We use `black` (for Python code) and `prettier` (for JS/TS/Vue) to automatically and consistently format the source code.
Please configure your favorite editor/IDE to format on save. 

## Observation import mechanism

The observation data shown in the webapp can be automatically updated by running the `import_observations` management 
command. This one will trigger a GBIF Download for our search of interest (based on the predicate builder function from the config file) and 
load the corresponding observations into the database. At the end of the process, observations from previous data 
imports are deleted, to avoid duplicates.

The data import history is recorded with the DataImport model, and shown to the user on the "about" page.

=> For a given observation, Django-managed IDs are therefore not stable. A hashing mechanism (based on `occurrenceId` 
and `DatasetKey`) to allow recognizing a given observation is implemented (`stable_id` field on Observation).

## Areas import mechanism

The application allows storing Areas (multipolygons) in the database for observation filtering and to display as map 
overlays. Each area can be either user-specific, either public. For now, there are 
3 ways to load a new area in the system:

- Administrators can use the Admin section to hand-drawn the area over an OSM background
- Administrators with a shell access The custom `load_area` management command can be used to directly import complex polygons from a file 
  source (shapefile, GeoJSON, ...)
- Users can upload their own areas via the web interface (development in progress
  
### How to use the `load_area` command to import a new public Area

1) Copy the source data file to `source_data/public_areas`
2) Adjust the `LAYER_MAPPING_CONFIGURATION` constant in `load_area.py` so it can deal with the specificities 
   of the new source file (other adjustments to `load_area.py` may also be necessary, see 
   [LayerMapping documentation](https://docs.djangoproject.com/en/3.2/ref/contrib/gis/layermapping/).)
3) Run `$ python manage.py load_area <my_source_file>`


## Users

The web application handle three categories of users:

- Anonymous users can access the website and visualize the observation data via the dashboard. For Django, they are 
  unauthenticated.
- Registered "normal" users can do all what can anonymous users can do + create and configure their alerts. Those users can 
  sign up directly thanks to a specific form (an e-mail address is required because it is needed for e-mail 
  notifications). For Django, they are regular users without any specific group or permission (**not** 
  staff, **not** superuser)
- Admins can do all that registered users can do + access the admin interface to configure the web application. For 
  Django, they have the **staff** and **superuser** flags set. Admins can be created by different means, for example 
  being upgraded to this status by an existing Admin after registering as a normal user, or via Django's 
  `createsuperuser` management command.
  
## Use of the messages framework

We make use of [Django's message framework](https://docs.djangoproject.com/en/3.2/ref/contrib/messages/), and the 
base template is configured to display a nice Bootstrap alert for the following message levels: `info`, `success`, 
`warning` and `error`.

Example use:
```
from django.contrib import messages

def my_view(request):
  ...
  messages.success(request, "Your profile was successfully updated.")
  return redirect("dashboard:pages:index")
```

## Use of Redis

Redis is currently used with [django-rq](https://github.com/rq/django-rq) to manage queues for long-running tasks 
(as of 2023-08: mark all observations as seen).

In addition to install a Redis instance on your development machine, you'll need to configure Django-rq to find it
(see local_settings.template.py) and run a worker for the default queue with ``$ python manage.py rqworker default``

## Maintenance mode

We make use of [django-maintenance-mode](https://github.com/fabiocaccamo/django-maintenance-mode). 

Maintenance mode will be set during each (observation) data import (data would be inconsistent at this stage, so we don't
want to let users access the website, nor send e-mail notifications).

This tool can also be used to manually activate maintenance mode during complex maintenance tasks, look at 
[django-maintenance-mode documentation](https://github.com/fabiocaccamo/django-maintenance-mode).

## Internationalization (i18n)

- For template-based / backend translations, we use the standard Django i18n tools (see [Django documentation](https://docs.djangoproject.com/en/4.1/topics/i18n/)) 
- (don't forget the translation for the notification e-mails: see `dashboard/templates/dashboard/emails` )
- For Vue components, we use https://vue-i18n.intlify.dev/ instead.
- Data-related translations that should be provided directly in the database via Django Admin: page fragments, vernacular names, ...

### How to update translations: Django
- In code, use the appropriate `gettext` functions (e.g. `_()`, `gettext()`, `ngettext()`, etc.), the `trans` template tag, etc.
- Update PO files with `$ python manage.py makemessages --ignore="node_modules/*" -l fr -l nl`
- Fill in the translations in the PO files
- Compile the PO files to MO with `$ python manage.py compilemessages`

### How to update translations: Vue
- Update the `messages` object in assets/ts/translations.ts. Please keep the keys in alphabetical order.

## How to release a new version

- Make sure all tests pass and mypy doesn't report any error
- Update CHANGELOG.md
- Update version number in `pyproject.toml`, `package.json` and `docker-compose.yml` (! 3 services: gbif-alert, rqworker and nginx)
- ! The version number currently also appears in INSTALL.md
- Commit, merge to main, push to GitHub
- Create a new tag (e.g. `v1.1.0`) and push it:
```
$ git tag v1.1.0
$ git push origin --tags
```
- Create a new Docker image and push it to Docker Hub (so end-users can reference it from docker-compose.yml):
- (We also build a new version of the nginx image - even if unchanged - so the version number of the two images stay in sync)
```
$ docker build . -t niconoe/gbif-alert:1.1.0
$ docker build ./nginx -t niconoe/gbif-alert-nginx:1.1.0
$ docker push niconoe/gbif-alert:1.1.0
$ docker push niconoe/gbif-alert-nginx:1.1.0
```

## How to link to a GBIF alert instance with specific filters

The URL format is: `<GBIF_ALERT_INSTANCE>/?filters=<filters>`

The following filters can be specified:
- 
- speciesIds: list of species IDs (integer)
- datasetsIds: list of dataset IDs (integer)
- areaIds: list of area IDs (integer)
- initialDataImportIds: list of data import IDs (integer)

Examples:

- https://alert.riparias.be/?filters={'speciesIds':[2,14,15]}
- https://alert.riparias.be/?filters={'speciesIds':[2,14,15],'areaIds':[1]}