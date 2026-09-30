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
if [ ! -e apps/pai_frappe ]; then
  bench get-app --soft-link --skip-assets "$app_path"
fi

if ! bench --site "$site_name" list-apps | grep -qx pai_frappe; then
  bench --site "$site_name" install-app pai_frappe
fi

bench --site "$site_name" migrate

cat <<'EOF'
PAI bridge is installed.
Next, configure PAI Settings and PAI User Identity in LMS Desk. For a host-run local Bench,
use http://127.0.0.1:18000 and enable Allow Insecure Local PAI URL in developer mode.
EOF
