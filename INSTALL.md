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