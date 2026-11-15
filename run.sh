#!/bin/sh
# Start Slipday.  Usage: sh run.sh [port]      (Linux and macOS; on Windows use run.ps1)
# MALLOC_ARENA_MAX=2 keeps glibc from holding freed memory in one arena per thread: with it the 240 m
# configuration stays under 512 MB under a burst of requests, without it it does not.
export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
exec python3 -m uvicorn slipday.api:app --host "${HOST:-127.0.0.1}" --port "${1:-${PORT:-8000}}"
