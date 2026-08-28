FROM alpine:latest

COPY ./reference-stac/ /reference-stac

RUN find /reference-stac -type f ! -name "*.json" -delete

