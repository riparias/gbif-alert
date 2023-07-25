Installing a GBIF Alert instance allows you to target a specific community of users, and to customize 
the website content to their needs.

Things that can be customized:
- Which subset of GBIF occurrences to monitor (e.g. only occurrences of a curated list of invasive species in Belgium). Those are the occurrences that will be imported in the database. 
Your end-users will be able to filter those occurrences further to match their specific needs.
- The available languages in the interface (currently English and French, Dutch will be added soon)
- Website texts (e.g. the introduction on the home page, the "about this site" page, etc.)

Technically speaking, GBIF Alert is a Django-based website, with the following dependencies:

- Python 3.11+
- PostgreSQL with PostGIS 3.1+
- Redis
- Access to an SMTP server (for sending notification emails)

While a manual installation is possible, we recommend using Docker Compose to install and run GBIF Alert. It will make your life much easier!

# Run GBIF Alert through Docker Compose

## Prerequisites:
- Make sure Docker is installed on your system: https://docs.docker.com/get-docker/
- Identify the latest release of GBIF Alert on GitHub at https://github.com/riparias/gbif-alert/tags (currently v1.1.1)

## Installation steps:

### Base installation
- Create a new directory on your system (`gbif-alert` for example)
- Get the docker-compose.yml file from the latest release of GBIF Alert on GitHub (https://github.com/riparias/gbif-alert/blob/v1.1.1/docker-compose.yml) 
and save it to the directory you just created (note that the URL contains the version number we've identified earlier).
- Get the local_settings_docker.template.py file from the latest release of GBIF Alert on GitHub (https://github.com/riparias/gbif-alert/blob/v1.1.1/djangoproject/local_settings_docker.template.py)
and also save it to the `gbif-alert` directory. Rename it to `local_settings_docker.py`.
- Open a terminal, navigate to the `gbif-alert` directory and run the following command: `docker-compose up`
This will take a while, and you'll see logs from multiple Docker containers. Once it stabilizes, keep this terminal open, and open a second one for subsequent commands.
Congratulations, you can now access your instance at http://localhost:1337

### Next steps
- Create a first superuser (administrator): in the second terminal, run the following command: `docker-compose exec gbif-alert poetry run python manage.py createsuperuser` and answer the questions.
After this, you can now sign in to the GBIF alert sign, and also access the Admin interface (at http://localhost:1337/admin, or via the link in the user menu, at the right of the top navigation bar).
- Create a few species in the Admin interface.
- You can now run the first data import from GBIF. In the second terminal, run the following command: `docker-compose exec gbif-alert poetry run python manage.py import_observations`



Here is detailed installation guide:

- Create the postgres database + user (use DO documentation)
- Set the necessary Python version:
$ pyenv local 3.11
- Install the necessary Python packages:
$ poetry install

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