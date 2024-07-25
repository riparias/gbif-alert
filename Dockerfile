FROM python:3.11-slim

RUN apt-get update
RUN apt-get install -y libgdal-dev git curl

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.3 \
    NVM_VERSION=0.39.1 \
    NVM_DIR=/root/.nvm \
    NODE_VERSION=19.7.0 \
    DJANGO_SETTINGS_MODULE=djangoproject.local_settings_docker

RUN mkdir /app
RUN mkdir /app/staticfiles
WORKDIR /app

RUN pip install "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root

COPY . /app

SHELL ["/bin/bash", "--login", "-c"]
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v$NVM_VERSION/install.sh | bash \
    && . $NVM_DIR/nvm.sh \
    && nvm install $NODE_VERSION \
    && nvm alias default $NODE_VERSION \
    && nvm use default \
    && node -v \
    && npm -v \
    && npm install \
    && npm run webpack-prod

ENTRYPOINT ["./docker-entrypoint.sh"]