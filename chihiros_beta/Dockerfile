ARG BUILD_ARCH=amd64
ARG BUILD_FROM=ghcr.io/home-assistant/${BUILD_ARCH}-base:latest
FROM ${BUILD_FROM}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apk add --no-cache \
    android-tools \
    bash \
    bluez \
    dbus \
    git \
    py3-pip \
    python3 \
    py3-virtualenv \
    tshark \
  && python3 -m venv /opt/chihiros-led-core-venv \
  && /opt/chihiros-led-core-venv/bin/pip install --no-cache-dir --upgrade pip \
  && /opt/chihiros-led-core-venv/bin/pip install --no-cache-dir \
    "bleak>=2" \
    bleak-retry-connector==4.6.1 \
    "click<8.2" \
    rich==13.9.4 \
    typer==0.15.2

COPY run.sh /run.sh
COPY ui /opt/chihiros-led-core-ui

RUN chmod a+x /run.sh \
  && printf '%s\n' '#!/usr/bin/env bash' 'export PYTHONPATH=/opt/chihiros-led-core-src/src:/opt/chihiros-led-core-src/custom_components/chihiros/vendor:/opt/chihiros-led-core-src:${PYTHONPATH}' 'exec /opt/chihiros-led-core-venv/bin/python /opt/chihiros-led-core-ui/chihirosctl_runner.py "$@"' > /usr/bin/chihirosctl \
  && chmod a+x /usr/bin/chihirosctl

ENV PYTHONPATH=/opt/chihiros-led-core-src/src:/opt/chihiros-led-core-src/custom_components/chihiros/vendor:/opt/chihiros-led-core-src
CMD ["/usr/bin/with-contenv", "bash", "/run.sh"]
