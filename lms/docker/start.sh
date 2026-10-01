#!/usr/bin/env bash

set -Eeuo pipefail

BENCH_DIR="${BENCH_DIR:-/home/frappe/frappe-bench}"
PROXY_PORT="${PROXY_PORT:-8000}"
BENCH_WEB_PORT="${BENCH_WEB_PORT:-8001}"

cd "${BENCH_DIR}"

bench start &
bench_pid=$!

python3 /usr/local/bin/lms-tcp-proxy.py \
	--listen-host 0.0.0.0 \
	--listen-port "${PROXY_PORT}" \
	--target-host 127.0.0.1 \
	--target-port "${BENCH_WEB_PORT}" &
proxy_pid=$!

cleanup() {
	kill "${proxy_pid}" "${bench_pid}" 2>/dev/null || true
	wait "${proxy_pid}" 2>/dev/null || true
	wait "${bench_pid}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

wait "${bench_pid}"
