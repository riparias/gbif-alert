Pterois is a Django-based website, with the following dependencies:

- Python 3.11+
- PostgreSQL with PostGIS 3.1+
- Redis
- Access to an SMTP server (for sending notification emails)

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

The easiest way to run Pterois is through Docker Compose. The following
instructions assume that you have Docker and Docker Compose installed on your
system.

1. Copy the file `docker-compose.yml` to your local directory
2. Copy the file `djangoproject/local_settings_docker.template.py` to your local directory and rename it to `local_settings_docker.py`
3. Tweak this file as necessary (see comments in the file)
2. $ run docker-compose up (keep this terminal open, and open a second one for subsequent commands)
3. Create a first superuser (administrator):
$ docker-compose exec pterois poetry run python manage.py createsuperuser
4. Create a few species before running the first import (see below)
5. Run the first import:
6. $ docker-compose exec pterois poetry run python manage.py import_observations