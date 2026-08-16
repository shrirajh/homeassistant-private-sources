ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN apk add --no-cache \
        ca-certificates \
        git \
        openssh-client

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

COPY rootfs /
COPY app /opt/psm

# Git on Windows does not reliably carry the exec bit into the build context.
RUN chmod a+x /etc/s6-overlay/s6-rc.d/psm/run \
              /etc/s6-overlay/s6-rc.d/psm/finish \
              /opt/psm/psm/bin/askpass.sh

WORKDIR /opt/psm
