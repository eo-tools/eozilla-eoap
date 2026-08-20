FROM ghcr.io/osgeo/gdal:ubuntu-small-3.13.3-amd64

ENV DEBIANFRONTEND=noninteractive

RUN apt update && \
    apt install -y --no-install-suggests \
        r-base r-base-core r-base-dev file r-cran-jsonlite r-cran-purrr libproj-dev libproj25 libudunits2-dev libgeos-dev libsqlite3-dev jq python3-pystac libuv1-dev libuv1t64 && \
     rm -rf /var/lib/apt/lists/*

RUN Rscript -e "install.packages(c('terra', 'raster', 'tmap', 'rstac'))"

COPY scripts/ /scripts/
