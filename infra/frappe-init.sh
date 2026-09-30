#!/usr/bin/env bash
set -euo pipefail

bench_path=/workspace/bench
site_name=${FRAPPE_SITE:?FRAPPE_SITE is required}

if [ ! -d "$bench_path/apps/frappe" ]; then
  bench init --skip-redis-config-generation "$bench_path"
fi

cd "$bench_path"
bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis-cache:6379
bench set-redis-queue-host redis://redis-queue:6379
bench set-redis-socketio-host redis://redis-socketio:6379

install_local_app() {
  app_name=$1
  app_path=$2
  if [ ! -e "apps/$app_name" ]; then
    bench get-app --soft-link --skip-assets "$app_path"
  fi
}

install_local_app lms /workspace/source/apps/lms
install_local_app pai_frappe /workspace/source/apps/pai_frappe

if [ ! -d "sites/$site_name" ]; then
  bench new-site "$site_name" \
    --mariadb-root-password "$FRAPPE_DB_ROOT_PASSWORD" \
    --admin-password "$FRAPPE_ADMIN_PASSWORD" \
    --no-mariadb-socket
fi

install_site_app() {
  app_name=$1
  if ! bench --site "$site_name" list-apps | grep -qx "$app_name"; then
    bench --site "$site_name" install-app "$app_name"
  fi
}

install_site_app lms
install_site_app pai_frappe
bench --site "$site_name" set-config developer_mode 1
bench --site "$site_name" clear-cache
bench use "$site_name"
exec bench start
