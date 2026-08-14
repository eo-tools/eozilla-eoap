FROM python:3.14-alpine

LABEL org.opencontainers.image.title="Dockerized Calculation of Primes with Python" \
      org.opencontainers.image.version="0.0.2" \
      org.opencontainers.image.authors="Florian Katerndahl <florian@katerndahl.com>" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/eo-tools/eozilla-eoap"

LABEL com.github.eozilla.eoap.cwlVersion="v1.2" \
      com.github.eozilla.eoap.processIdentifier="primes-workflow"

RUN pip install pydantic

COPY primes.py /primes.py