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