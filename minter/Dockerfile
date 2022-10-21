# syntax = docker/dockerfile:1.4
FROM python:3.10-slim-bullseye

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get -y upgrade && \
    apt-get install -y --no-install-recommends tini && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home appuser
USER appuser

WORKDIR /app
COPY . .

ENV PYTHONFAULTHANDLER=1
ENTRYPOINT ["tini", "--", "uvicorn", "app.main:app", "--reload"]