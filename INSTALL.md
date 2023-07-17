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



# Run through Docker Compose

The easiest way to run Pterois is through Docker Compose. The following
instructions assume that you have Docker and Docker Compose installed on your
system.

1. Obtain the Pterois source code (download a release or clone the repository)
2. $ run docker-compose up (keep this terminal open, and open a second one for subsequent commands)
3. Create a first superuser (administrator):
$ docker-compose exec pterois poetry run python manage.py createsuperuser