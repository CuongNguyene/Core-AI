#!/usr/bin/env bash
set -euo pipefail

compose_files=(
  devops/database/docker-compose.yml
  devops/redis/docker-compose.yml
  devops/minio/docker-compose.yml
  devops/backend/docker-compose.yml
  devops/nginx/docker-compose.yml
)

for compose_file in "${compose_files[@]}"; do
  test -f "$compose_file"
  docker compose --env-file "$(dirname "$compose_file")/.env.example" \
    -f "$compose_file" config --quiet
done

grep -q 'postgres:18' devops/database/docker-compose.yml
grep -q '/var/lib/postgresql' devops/database/docker-compose.yml
grep -q -- '--appendonly yes' devops/redis/docker-compose.yml
grep -q -- '--requirepass' devops/redis/docker-compose.yml
grep -q '^name: pai-database$' devops/database/docker-compose.yml
grep -q '^name: pai-redis$' devops/redis/docker-compose.yml
grep -q '^name: pai-minio$' devops/minio/docker-compose.yml
grep -q '^name: pai-backend$' devops/backend/docker-compose.yml
grep -q '^name: pai-nginx$' devops/nginx/docker-compose.yml
