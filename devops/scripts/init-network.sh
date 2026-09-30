#!/usr/bin/env bash
set -euo pipefail

if ! docker network inspect pai-proxy >/dev/null 2>&1; then
  docker network create pai-proxy
fi
