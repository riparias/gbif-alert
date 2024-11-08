# Deploy a GBIF Alert instance

Deploying a GBIF Alert instance allows you to target a specific community of users by:
- Defining the taxonomic, temporal and spatial scope of the alert tool.
- Customize the website content.

## Customizable parts

You can customize:

- The subset of [GBIF occurrences](https://www.gbif.org/occurrence/) to monitor, e.g.
only [occurrences of the 5 invasive alien fishes in New Zealand](https://www.gbif.org/occurrence/search?country=NZ&taxon_key=2367196&taxon_key=2350580&taxon_key=2362635&taxon_key=2340989&taxon_key=8215487). Those are the **only** occurrences that GBIF Alert 
will periodically download from GBIF and will import in its database.
- Your end-users will be able to filter those occurrences further to match their specific needs.
- The available languages in the interface: currently English and French are supported, other languages will be added soon.
- Website texts, e.g. the introduction on the home page, the footer content and the "about this site" page.
- Some visual elements such as the navbar color.

## Dependencies

Technically speaking, GBIF Alert is a [Django](https://www.djangoproject.com/)-based website, with the following dependencies:

- [Python](https://www.python.org/)
- [PostgreSQL](https://www.postgresql.org/) with [PostGIS](https://postgis.net/)
- [Redis](https://redis.io/)
- [NPM](https://www.npmjs.com/) (for frontend assets)

(see [CONTRIBUTING.md](CONTRIBUTING.md) for specific versions and more details on the inner working of the tool).

While a manual installation of those components is possible, we recommend using [Docker Compose](https://docs.docker.com/get-started/08_using_compose/) to install and run GBIF Alert. 
It will make your life much easier!

Please note that in order to run a production GBIF Alert instance, you will need to have access to the following resources:

- A server running Linux with a public IP address (and a domain name)
- Access to an [SMTP server](https://nl.wikipedia.org/wiki/Simple_Mail_Transfer_Protocol) (for sending notification emails)

## Install and run GBIF Alert through Docker Compose

Installing GBIF Alert through Docker Compose is the recommended way to install and run GBIF Alert. It is suitable for
a quick test or a production deployment. It will install all the dependencies for you and will make sure they are
properly configured.

### Prerequisites

- Make sure [Docker](https://docs.docker.com/get-docker/) is installed on your system
- Identify the latest release of GBIF Alert on GitHub at https://github.com/riparias/gbif-alert/tags (currently [v1.7.7](https://github.com/riparias/gbif-alert/releases/tag/v1.7.7))

### Installation steps

- Create a new directory on your system, e.g. `invasive-fishes-nz` following the example above.
- Go to the `docker-compose.yml` file from the latest release of GBIF Alert on GitHub: at the moment https://github.com/riparias/gbif-alert/blob/v1.7.7/docker-compose.yml (note that the URL contains the version number).
- Save the file in the directory you have just created.
- Go to the `local_settings_docker.template.py` file from the latest release of GBIF Alert on GitHub: at the moment https://github.com/riparias/gbif-alert/blob/v1.7.7/djangoproject/local_settings_docker.template.py.
- Save the file in the directory you have just created. 
- Rename this file to `local_settings_docker.py`.
- Open a terminal, navigate to the `invasive-fishes-nz` directory and run the following command: `docker-compose up`. 

- The first execution will take a while, and you'll see logs from multiple Docker containers. Don't close this terminal. Once it stabilizes, open a second terminal for subsequent commands.

Congrats, 👏 you can now access your instance at `http://localhost:1337`.

### Next step: customization your GBIF Alert instance

- With your favourite text editor, open the `local_settings_docker.py` file you have just created.
- Edit it to customize the following settings:
  - The `GBIF_ALERT` dictionary is heavily commented and should be self-explanatory. It contains settings such as the site name, the credentials used to 
  download occurrences from GBIF, ...
  - A special attention point for the `GBIF_ALERT['GBIF_DOWNLOAD_CONFIG']['PREDICATE_BUILDER'']` setting: it defines the subset of GBIF occurrences that will be downloaded and imported in the GBIF Alert database. You need to provide a function that returns a GBIF predicate. You can get inspiration from `build_gbif_download_predicate()`. Please note that this function will receive a list of species at runtime, so it's important to keep the "TAXON_KEY IN (...)" part of predicate similar to the example function.
- For production websites, you should also take care of the following settings:
  - `SECRET_KEY` must be set. See the [Django documentation](https://docs.djangoproject.com/en/4.2/ref/settings/#std-setting-SECRET_KEY) for more details.
  - Once confirmed that your instance is working properly, switch `DEBUG` to `False`.
  - `SITE_BASE_URL` should be set to the base URL of your website, e.g. `https://invasive-fishes-nz.org`. This is used to generate links in the notification e-mails.
  - The `EMAIL_*` settings are used to send notification e-mails. Please refer to the [Django documentation](https://docs.djangoproject.com/en/4.2/ref/settings/#email) for more details.
- Save the file.
- You might need to stop (CTRL+C) and restart (run `docker-compose up` again) the Docker Compose stack in the first terminal to take the changes into account. This is especially true if you have set `DEBUG` to `False`.

### Next step: create a first superuser, add a few species and import occurrence data from GBIF

- Create a first superuser or **administrator**: in the second terminal, run the following command: `docker-compose exec gbif-alert poetry run python manage.py createsuperuser` and answer the questions.
- Log in to the GBIF Alert instance you have just created. You can access to the Admin interface at `http://localhost:1337/admin`, or via the "Admin panel" link in the dropdown menu of the navigation bar on the top right.
- Add the species you are interested to via the Admin panel. You will probably need to use the [GBIF species](https://www.gbif.org/species/) webpage to get the taxon keys. 
- You are all set up to run the first data import from GBIF! 🚀 In the second terminal, run the following command: `docker-compose exec gbif-alert poetry run python manage.py import_observations`. This will take some time (a couple of minutes to a couple of hours).
- After completion, you go back to your instance (http://localhost:1337) and start exploring the data.
- Note that you'll need to run the import command periodically to keep your instance up-to-date. Since your instance will be in maintenance mode during (part of) the import, you might want to schedule the import command to run at night.

### Next step: Create alerts, test e-mail notifications

- Create a new alert via the "My alerts" page.
- Make sure you have a valid e-mail address in your user profile and some unseen occurrences in your alert.
- In the second terminal, run the following command: `docker-compose exec gbif-alert poetry run python manage.py send_alert_notifications_email`. This will send a notification e-mail to your e-mail address.
- Similar to the import command, you'll need to run the notification command periodically to send notifications to your users. This will not work if your instance is still importing data from GBIF, so you'll want to schedule the notification command to run after the import command (with some margin).

### Next step: customize the website content (texts)

### Next steps: load a few areas of interest

## Run GBIF Alert manually

You don't like Docker and do you prefer to have full control on everything? Great!

You'll need to install Python, PostgreSQL, PostGIS and Redis on your system. Please refer to [CONTRIBUTING.md](CONTRIBUTING.md) for the specific versions required. 

You'll also need to:

- Create the database and install the PostGIS extension.
- Adjust Django settings appropriately, you can use `local_settings.template.py` as a starting point.
- Create a virtual environment and install the Python dependencies: `$ poetry install`.
- Generate the database schema: `$ poetry run python manage.py migrate` before the first execution.
- Install frontend dependencies: `$ npm install`.
- Generate static assets: `$ npm run webpack-prod`.
- Compile translations: `$ poetry run python manage.py compilemessages`.
- Run Django through Gunicorn (or your favourite WSGI server), and place a reverse proxy in front of it (e.g. Nginx).
- Install two Cron jobs:
  - One to periodically download occurrences from GBIF and import them in the database: `$ poetry run python manage.py import_observations`
  - One to periodically send notification e-mails: `$ poetry run python manage.py send_alert_notifications_email`
- Run  rqworker in the background to process long-running tasks: `$ poetry run python manage.py rqworker default`
