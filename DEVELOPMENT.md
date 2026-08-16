# Development

Local development uses [uv](https://docs.astral.sh/uv/). The add-on image itself is built by
the Supervisor on the device and only uses pip, from a pinned `requirements.txt` exported
from the uv lockfile.

## Setup

```bash
uv sync
```

## Run locally

`PSM_DEV=1` disables the ingress peer check and redirects the Supervisor paths
(`/data`, `/homeassistant`, `/addons`) into `./.dev/`, so nothing outside the repo is touched.

```bash
PSM_DEV=1 uv run python -m psm
```

Then open <http://127.0.0.1:8099>.

Override individual paths with `PSM_DATA_DIR`, `PSM_HA_CONFIG_DIR`, `PSM_ADDONS_DIR`,
or move the whole sandbox with `PSM_DEV_ROOT`.

## Tests and lint

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Changing dependencies

`pyproject.toml` and `uv.lock` are the source of truth. After any dependency change,
regenerate the pinned file the image installs from and commit it:

```bash
uv export --no-dev --no-emit-project --no-hashes --no-annotate \
  -o private_source_manager/requirements.txt
```

Only add dependencies that publish `musllinux` wheels for **aarch64**. Anything else
compiles from source on the Home Assistant Green, which is slow at best and fails at worst.
This is why the architecture list is `aarch64` and `amd64` only: `cryptography` publishes no
musllinux wheel for armv7.

## Building the image locally

The Supervisor supplies `BUILD_FROM` from `build.yaml`. To reproduce a build on an amd64
workstation:

```bash
docker build \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.13-alpine3.23-2026.06.1 \
  -t psm-test:local private_source_manager
```

## Line endings

`.gitattributes` forces LF. The s6 service scripts under `rootfs/` carry shebangs, so a CRLF
checkout on Windows would produce a container that fails to start.
