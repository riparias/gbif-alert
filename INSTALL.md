# Deploy a GBIF Alert instance

Deploying a GBIF Alert instance allows you to target a specific community of users by:
- Defining the taxonomic, temporal and spatial scope of the alert tool.
- Customize the website content.


## Customizable parts

You can customize:

- The subset of [GBIF occurrences](https://www.gbif.org/occurrence/) to monitor, e.g. only occurrences of ladybirds in New Zealand observed after 2010. Those are the **only** occurrences that GBIF Alert will periodically donwload from GBIF and will import in the database.
Your end-users will be able to filter those occurrences further to match their specific needs.
- The available languages in the interface: currently English and French are supported, other languages will be added soon.
- Website texts, e.g. the introduction on the home page, the footnote message and the "about this site" page.


## Dependencies

Technically speaking, GBIF Alert is a [Django](https://www.djangoproject.com/)-based website, with the following dependencies:

- [Python](https://www.python.org/) 3.11+
- [PostgreSQL](https://www.postgresql.org/) with [PostGIS](https://postgis.net/) 3.1+
- [Redis](https://redis.io/)
- Access to an [SMTP server](https://nl.wikipedia.org/wiki/Simple_Mail_Transfer_Protocol) (for sending notification emails)

While a manual installation is possible, we recommend using [Docker Compose](https://docs.docker.com/get-started/08_using_compose/) to install and run GBIF Alert. It will make your life much easier! So, read further, please!


## Run GBIF Alert through Docker Compose

### Prerequisites

- Make sure [Docker](https://docs.docker.com/get-docker/) is installed on your system
- Identify the latest release of GBIF Alert on GitHub at https://github.com/riparias/gbif-alert/tags (currently [v1.1.2](https://github.com/riparias/gbif-alert/releases/tag/v1.1.2))


### Installation steps


- Create a new directory on your system, e.g. `gbif-alert` or `ladybirds-watch-nz` following the example above.
- Go to the `docker-compose.yml` file from the latest release of GBIF Alert on GitHub: at the [`moment docker-compose.yml` v1.1.2]( https://github.com/riparias/gbif-alert/blob/v1.1.2/docker-compose.yml). Note that the URL contains the version number.
- Save the file in the directory you have just created.
- Go to the `local_settings_docker.template.py` file from the latest release of GBIF Alert on GitHub: at the moment [`local_settings_docker.template.py` v1.1.2](https://github.com/riparias/gbif-alert/blob/v1.1.2/djangoproject/local_settings_docker.template.py).
- Save the file in the directory you have just created. Rename it to `local_settings_docker.py`.
- Open a terminal, navigate to the `gbif-alert` directory and run the following command: `docker-compose up`. This will take a while and you'll see logs from multiple Docker containers. Do **never** close this terminal. Once it stabilizes, open a second terminal for subsequent commands.

Congrats, 👏 you can now access your instance at `http://localhost:1337`.


### Settings and customization

- Create a first superuser or **administrator**: in the second terminal, run the following command: `docker-compose exec gbif-alert poetry run python manage.py createsuperuser` and answer the questions.
- Log in to the GBIF Alert instance you have just created. You can access to the Admin interface at `http://localhost:1337/admin`, or via the "Admin panel" link in the drop down menu of the navigation bar on the top right.
- Add the species you are interested to via the Admin panel. You will probably need to use the [GBIF species](https://www.gbif.org/species/) webpage to get the taxon keys. 
- You are all set up to run the first data import from GBIF! 🚀 In the second terminal, run the following command: `docker-compose exec gbif-alert poetry run python manage.py import_observations`.


## Run GBIF Alert manually

Don't you like Docker and do you prefer to have fully control on everything? Great! Follow the next steps:

- Create the postgres database + user (use DO documentation)
- Set the necessary Python version: `$ pyenv local 3.11`.
- Install the necessary Python packages: `$ poetry install`.

To add/ describe:

- configure local_settings.py
- create initial superuser
- create a few species before running the first import
- install the cronjob for the import
- test e-mail sending
- install the cronjob for the email notifications
- configure required page fragments in the admin


TODO next Docker:

- Polish documentation
- Add more steps (create species, run first import, etc.)
- Push images to dockerhub

# Run through Docker Compose

The easiest way to run GBIF Alert is through Docker Compose. The following
instructions assume that you have Docker and Docker Compose installed on your
system.

1. Copy the file `docker-compose.yml` to your local directory
2. Copy the file `djangoproject/local_settings_docker.template.py` to your local directory and rename it to `local_settings_docker.py`
3. Tweak this file as necessary (see comments in the file)
2. $ run docker-compose up (keep this terminal open, and open a second one for subsequent commands)
3. Create a first superuser (administrator):
$ docker-compose exec gbif-alert poetry run python manage.py createsuperuser
4. Create a few species before running the first import (see below)
5. Run the first import:
6. $ docker-compose exec gbif-alert poetry run python manage.py import_observations
