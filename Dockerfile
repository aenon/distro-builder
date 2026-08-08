FROM docker:27-cli AS docker-source

FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        qemu-utils \
        genisoimage \
        xorriso \
        grub-pc-bin \
        grub-efi-amd64-bin \
        dracut-core \
        curl \
        ca-certificates \
        file && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=docker-source /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-source /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install .

WORKDIR /workspace
VOLUME ["/workspace"]

ENTRYPOINT ["distro-builder"]
CMD ["--help"]
