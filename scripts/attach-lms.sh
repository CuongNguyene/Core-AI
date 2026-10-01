#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --bench /path/to/frappe-bench --site site-name" >&2
  exit 2
}

bench_path=
site_name=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --bench)
      bench_path=${2:-}
      shift 2
      ;;
    --site)
      site_name=${2:-}
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

[ -n "$bench_path" ] && [ -n "$site_name" ] || usage
[ -d "$bench_path/apps" ] || {
  echo "Frappe Bench not found: $bench_path" >&2
  exit 1
}

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
app_path=$(cd -- "$script_dir/../apps/pai_frappe" && pwd)

cd "$bench_path"
# Core-AI is a monorepo, so apps/pai_frappe is not itself a standalone git
# repository. Bench's get-app treats that local path as an app name under
# newer Bench releases; link the app directory directly instead.
if [ ! -e apps/pai_frappe ] && [ ! -L apps/pai_frappe ]; then
  ln -s "$app_path" apps/pai_frappe
fi

if ! grep -qx pai_frappe sites/apps.txt; then
	if [ -s sites/apps.txt ] && [ "$(tail -c 1 sites/apps.txt | wc -l)" -eq 0 ]; then
		printf '\n' >> sites/apps.txt
	fi
  printf '%s\n' pai_frappe >> sites/apps.txt
fi

bench setup requirements --python pai_frappe

if ! bench --site "$site_name" list-apps | grep -qx pai_frappe; then
  bench --site "$site_name" install-app pai_frappe
fi

bench --site "$site_name" migrate

cat <<'EOF'
PAI bridge is installed.
Next, configure PAI Settings and PAI User Identity in LMS Desk. For this Dockerized
Frappe setup, use http://host.docker.internal:18000 and enable Allow Insecure Local
PAI URL in developer mode.
EOF
