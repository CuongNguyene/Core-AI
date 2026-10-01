# Local-development-only MinIO image.
# The source tag and commit are pinned so this build never falls back to a
# registry-provided MinIO image or the upstream Dockerfile.

ARG MINIO_TAG=RELEASE.2025-09-07T16-13-09Z
ARG MINIO_COMMIT=07c3a429bfed433e49018cb0f78a52145d4bedeb

FROM golang:1.24.2-bookworm AS builder

ARG MINIO_TAG
ARG MINIO_COMMIT

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates git make perl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git init \
    && git remote add origin https://github.com/minio/minio.git \
    && git fetch --depth 1 origin "refs/tags/${MINIO_TAG}:refs/tags/${MINIO_TAG}" \
    && test "$(git rev-parse "${MINIO_TAG}^{commit}")" = "${MINIO_COMMIT}" \
    && git checkout --detach "${MINIO_COMMIT}"

RUN go mod verify

# This is the official MinIO Makefile build target, deliberately not
# `make docker`, whose Dockerfile depends on minio/minio:latest.
RUN MINIO_RELEASE=RELEASE GOOS=linux GOARCH=arm64 CGO_ENABLED=0 make build
RUN ./minio --version | grep -F "RELEASE.2025-09-07T16-13-09Z"

FROM alpine:3.20

COPY --from=builder /src/minio /usr/local/bin/minio

ENTRYPOINT ["/usr/local/bin/minio"]
VOLUME ["/data"]
CMD ["server", "/data", "--console-address", ":9001"]
