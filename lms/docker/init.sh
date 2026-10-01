#!/usr/bin/env bash

set -Eeuo pipefail

BENCH_DIR="${BENCH_DIR:-/home/frappe/frappe-bench}"
SITE_NAME="${SITE_NAME:-lms.localhost}"
APP_NAME="${APP_NAME:-lms}"
APP_PATH="${APP_PATH:-/workspace}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-15}"
DB_HOST="${DB_HOST:-mariadb}"
DB_ROOT_PASSWORD="${DB_ROOT_PASSWORD:-123}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
REDIS_URL="${REDIS_URL:-redis://redis:6379}"
INSTALL_REQUIREMENTS="${INSTALL_REQUIREMENTS:-1}"
BUILD_ASSETS="${BUILD_ASSETS:-1}"

if [[ "$(id -u)" == "0" ]]; then
	echo "Preparing Bench volume permissions..."
	mkdir -p "${BENCH_DIR}"
	chown -R frappe:frappe "${BENCH_DIR}"
	frappe_node_bin="$(find /home/frappe/.nvm/versions/node -mindepth 2 -maxdepth 2 -type d -name bin | sort -V | tail -n 1)"
	if [[ -z "${frappe_node_bin}" ]]; then
		echo "Unable to locate the Node.js toolchain in the Bench image" >&2
		exit 1
	fi
	exec sudo -H -E -u frappe env \
		"PATH=${frappe_node_bin}:/home/frappe/.local/bin:/home/frappe/.pyenv/shims:/home/frappe/.pyenv/bin:/usr/local/bin:/usr/bin:/bin" \
		"$0" "$@"
fi

export PATH="/home/frappe/.local/bin:/home/frappe/.pyenv/shims:/home/frappe/.pyenv/bin:${PATH}"

if [[ -n "${NVM_BIN:-}" ]]; then
	export PATH="${NVM_BIN}:${PATH}"
elif [[ -n "${NVM_DIR:-}" && -n "${NODE_VERSION_DEVELOP:-}" ]]; then
	export PATH="${NVM_DIR}/versions/node/v${NODE_VERSION_DEVELOP}/bin/:${PATH}"
elif [[ -n "${NVM_DIR:-}" && -n "${NODE_VERSION:-}" ]]; then
	export PATH="${NVM_DIR}/versions/node/v${NODE_VERSION}/bin/:${PATH}"
fi

if [[ ! -d "${BENCH_DIR}/apps/frappe" ]]; then
	echo "Creating Frappe Bench at ${BENCH_DIR}..."
	bench init --ignore-exist --frappe-branch "${FRAPPE_BRANCH}" --skip-redis-config-generation --skip-assets "${BENCH_DIR}"
fi

cd "${BENCH_DIR}"

echo "Configuring Bench services..."
bench set-mariadb-host "${DB_HOST}"
bench set-redis-cache-host "${REDIS_URL}"
bench set-redis-queue-host "${REDIS_URL}"
bench set-redis-socketio-host "${REDIS_URL}"

# The repository is mounted directly at apps/${APP_NAME} by Compose. Keep a
# symlink fallback for manual container runs that only mount /workspace.
if [[ ! -L "apps/${APP_NAME}" ]]; then
	if [[ ! -d "apps/${APP_NAME}" ]]; then
		ln -s "${APP_PATH}" "apps/${APP_NAME}"
	fi
fi

if ! grep -qxF "${APP_NAME}" sites/apps.txt; then
	printf '\n%s\n' "${APP_NAME}" >> sites/apps.txt
fi

# Redis is provided by the Compose service. Keep the asset watcher enabled for
# local debugging; it can be disabled with ENABLE_ASSET_WATCH=0.
sed -i '/redis/d' ./Procfile
sed -i -E 's/^web:.*$/web: bench serve --port 8001/' ./Procfile
if [[ "${ENABLE_ASSET_WATCH:-1}" != "1" ]]; then
	sed -i '/watch/d' ./Procfile
fi

if [[ "${INSTALL_REQUIREMENTS}" == "1" && ! -f .lms-requirements-ready ]]; then
	echo "Installing LMS requirements..."
	bench setup requirements --dev
	touch .lms-requirements-ready
fi

if [[ ! -f .lms-app-ready ]]; then
	echo "Installing ${APP_NAME} in editable mode..."
	uv pip install --quiet -e "apps/${APP_NAME}" --python "${BENCH_DIR}/env/bin/python"
	touch .lms-app-ready
fi

if [[ ! -f "sites/${SITE_NAME}/site_config.json" ]]; then
	echo "Creating site ${SITE_NAME}..."
	bench new-site "${SITE_NAME}" \
		--force \
		--mariadb-root-password "${DB_ROOT_PASSWORD}" \
		--admin-password "${ADMIN_PASSWORD}" \
		--no-mariadb-socket
fi

installed_apps="$(bench --site "${SITE_NAME}" list-apps)"
if ! printf '%s\n' "${installed_apps}" | awk -v app="${APP_NAME}" '$1 == app { found = 1 } END { exit !found }'; then
	echo "Installing ${APP_NAME} on ${SITE_NAME}..."
	bench --site "${SITE_NAME}" install-app "${APP_NAME}"
fi

bench --site "${SITE_NAME}" set-config developer_mode 1
bench --site "${SITE_NAME}" clear-cache
bench use "${SITE_NAME}"

if [[ "${BUILD_ASSETS}" == "1" && ! -f .lms-assets-ready ]]; then
	echo "Building LMS assets..."
	bench build --app "${APP_NAME}"
	touch .lms-assets-ready
fi

echo "Starting Frappe Bench for ${SITE_NAME}"
exec /usr/local/bin/lms-start.sh
