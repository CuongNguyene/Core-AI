# Local MinIO image

This image is for local PAI development only. It builds the official MinIO
source tag `RELEASE.2025-09-07T16-13-09Z` at commit
`07c3a429bfed433e49018cb0f78a52145d4bedeb` with the upstream Makefile `build`
target, then packages the resulting binary in a small runtime image.

It intentionally does not use the upstream `make docker` target or any MinIO
container image.
