#!/usr/bin/env bash
# Container check for Slipday: build the image, run it under a memory limit, ask for the first screen and
# one cold request, and print the peak memory of the container's memory group.
#
# NOT RUN by its author.  Written on 15 Nov 2026 on a machine where Docker was not started; only its syntax
# was checked (bash -n).  No figure in the README comes from this script yet.  Read its first output with care.
#
# One command, from anywhere:
#     bash scripts/container_check.sh [MEMORY] [PORT]
#         MEMORY   memory limit in Docker's notation (default 1g; also try 768m, 512m, 2g)
#         PORT     port published on this machine (default 8010)
# Settings (environment variables):
#     GRID80=1   when data/dem/ldem_80s_80m_f32.npy is absent, pass --build-arg GRID80=1 so that the build
#                downloads NASA's 80 m file (189 MB from pgda.gsfc.nasa.gov, sha256 checked, network needed).
#                Without it an image built from a folder that lacks the file runs on the 240 m grid.
#     KEEP=1     leave the container running at the end (for scripts/stress_check.py); default: stop, remove
#     IMAGE      image tag (default slipday-check)       NAME   container name (default slipday-check-<pid>)
#
# How the 80 m grid gets into the image (see the Dockerfile): "COPY . ." copies data/dem/ as it is, so a
# folder that has ldem_80s_80m_f32.npy gives an image that has it; .dockerignore does not exclude it.
#
# What it does: (a) docker build, (b) docker run with --memory MEMORY --memory-swap MEMORY --cpus 2 (swap
# equal to memory means no swap, so the limit is a hard one, as on a hosting plan), (c) waits for
# /api/health, (d) fetches the page, the stored opening card, the slip map for that date, one 3-D frame and
# one cold request (landing circles at a point no cache has seen), printing each status and time,
# (e) prints the peak of the memory group, whether the kernel killed the container for memory, and the
# image size, (f) stops and removes the container.
# This is the least a host must survive, not a load test.  For load: KEEP=1, then
#     python scripts/stress_check.py http://127.0.0.1:PORT --docker NAME
# Memory is printed in bytes and in MiB (1 MiB = 1,048,576 bytes), the unit stress_check.py and the
# first-pass table in the README call "MB".
set -u

MEM="${1:-1g}"
PORT="${2:-8010}"
IMAGE="${IMAGE:-slipday-check}"
NAME="${NAME:-slipday-check-$$}"
BASE="http://127.0.0.1:${PORT}"
LANDING="2026-11-18T00:00:00Z"
GRID="data/dem/ldem_80s_80m_f32.npy"

# Git Bash on Windows rewrites arguments that look like Unix paths; the paths below are inside the container.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

cd "$(dirname "$0")/.." || exit 2
command -v docker >/dev/null 2>&1 || { echo "docker is not on the PATH"; exit 2; }
command -v curl >/dev/null 2>&1 || { echo "curl is not on the PATH"; exit 2; }
docker info >/dev/null 2>&1 || { echo "the Docker engine is not running"; exit 2; }

echo "== build ($(date -u +%Y-%m-%dT%H:%M:%SZ)), folder $(pwd)"
if [ -f "$GRID" ]; then
  echo "80 m grid present ($GRID): the image will include it"
  docker build -t "$IMAGE" . || { echo "build failed"; exit 2; }
elif [ "${GRID80:-0}" = "1" ]; then
  echo "80 m grid absent: building with --build-arg GRID80=1 (downloads 189 MB, sha256 checked)"
  docker build --build-arg GRID80=1 -t "$IMAGE" . || { echo "build failed"; exit 2; }
else
  echo "80 m grid absent and GRID80 is not 1: THIS IMAGE RUNS ON THE 240 m GRID"
  docker build -t "$IMAGE" . || { echo "build failed"; exit 2; }
fi

cleanup() {
  if [ "${KEEP:-0}" = "1" ]; then
    echo "container $NAME left running on $BASE (KEEP=1); remove it with: docker rm -f $NAME"
  else
    docker stop -t 5 "$NAME" >/dev/null 2>&1
    docker rm -f "$NAME" >/dev/null 2>&1
    echo "container $NAME stopped and removed"
  fi
}
trap cleanup EXIT

echo "== run: --memory $MEM --memory-swap $MEM --cpus 2, port $PORT"
docker run -d --name "$NAME" --memory "$MEM" --memory-swap "$MEM" --cpus 2 -p "${PORT}:8000" "$IMAGE" >/dev/null \
  || { echo "docker run failed"; exit 2; }

running() { [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" = "true" ]; }

PEAK=""            # last reading of the memory group's peak, in bytes
PEAK_FROM=""
read_peak() {
  local v
  v="$(docker exec "$NAME" sh -c 'cat /sys/fs/cgroup/memory.peak 2>/dev/null' 2>/dev/null | tr -d '[:space:]')"
  if [ -n "$v" ]; then PEAK="$v"; PEAK_FROM="cgroup v2 memory.peak"; return; fi
  v="$(docker exec "$NAME" sh -c 'cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes 2>/dev/null' 2>/dev/null | tr -d '[:space:]')"
  if [ -n "$v" ]; then PEAK="$v"; PEAK_FROM="cgroup v1 memory.max_usage_in_bytes"; fi
}

mib() { echo "$(( $1 / 1048576 )) MiB"; }

echo "== wait for /api/health (up to 180 s)"
ok=0
i=0
while [ "$i" -lt 180 ]; do
  if ! running; then echo "the container stopped before it answered"; break; fi
  if curl -s -f -o /dev/null --max-time 5 "$BASE/api/health"; then ok=1; break; fi
  sleep 1
  i=$((i + 1))
done
FAIL=0
if [ "$ok" = "1" ]; then
  echo "healthy after about ${i} s"
  curl -s --max-time 10 "$BASE/api/health" | grep -o '"label": *"[^"]*"' | head -n 1
  curl -s --max-time 10 "$BASE/api/health" | grep -o '"malloc_arena_limit": *"[^"]*"' | head -n 1
else
  FAIL=1
  docker logs --tail 30 "$NAME" 2>&1
fi

# req LABEL METHOD PATH [JSON-BODY] [MAX-SECONDS]: one line with the status and the time
req() {
  local label="$1" method="$2" path="$3" body="${4:-}" limit="${5:-300}" out code secs
  if [ "$method" = "POST" ]; then
    out="$(curl -s -o /dev/null -w '%{http_code} %{time_total}' --max-time "$limit" \
            -H 'Content-Type: application/json' -X POST --data "$body" "$BASE$path")"
  else
    out="$(curl -s -o /dev/null -w '%{http_code} %{time_total}' --max-time "$limit" "$BASE$path")"
  fi
  code="${out%% *}"
  secs="${out##* }"
  read_peak
  printf '%-34s %-4s %-22s status %s  %s s  group peak %s\n' "$label" "$method" "$path" "$code" "$secs" \
    "$( [ -n "$PEAK" ] && mib "$PEAK" || echo 'not read' )"
  [ "$code" = "200" ] || FAIL=1
}

if [ "$ok" = "1" ]; then
  echo "== requests"
  req "page"                         GET  "/"
  req "stored opening card"          POST "/api/mission" "{\"site\":{\"id\":\"robust_pick\"},\"landing\":\"$LANDING\"}"
  req "slip map, 13-point re-check"  POST "/api/robust-map" "{\"start\":\"$LANDING\",\"n_dates\":60}" 900
  req "one 3-D frame"                GET  "/api/terrain3d?site=robust_pick&at=$LANDING" "" 600
  req "cold: landing circles, new point" POST "/api/landing-circles" \
      "{\"site\":{\"lat\":-86.4321,\"lon\":17.123},\"landing\":\"$LANDING\"}" 1800
  req "stored opening card again"    POST "/api/mission" "{\"site\":{\"id\":\"robust_pick\"},\"landing\":\"$LANDING\"}"
fi

echo "== memory"
if running; then
  read_peak
  if [ -n "$PEAK" ]; then
    echo "peak of the container's memory group: $PEAK bytes = $(mib "$PEAK")  ($PEAK_FROM), limit $MEM"
  else
    echo "no cgroup peak file could be read; docker stats gives the usage NOW, not a peak:"
    docker stats --no-stream --format '{{.Name}}  {{.MemUsage}}  {{.MemPerc}}' "$NAME"
  fi
  docker exec "$NAME" sh -c 'grep oom_kill /sys/fs/cgroup/memory.events 2>/dev/null' 2>/dev/null
else
  FAIL=1
  if [ -n "$PEAK" ]; then
    echo "the container is no longer running; last reading before it stopped: $PEAK bytes = $(mib "$PEAK")  ($PEAK_FROM)"
  else
    echo "the container is no longer running and no peak was read"
  fi
fi
OOM="$(docker inspect -f '{{.State.OOMKilled}}' "$NAME" 2>/dev/null)"
echo "killed by the kernel for memory (State.OOMKilled): ${OOM:-unknown}; exit code $(docker inspect -f '{{.State.ExitCode}}' "$NAME" 2>/dev/null)"
[ "$OOM" = "true" ] && FAIL=1
SIZE="$(docker image inspect -f '{{.Size}}' "$IMAGE" 2>/dev/null)"
if [ -n "$SIZE" ]; then
  echo "image $IMAGE: $SIZE bytes = $(( SIZE / 1000000 )) MB"
fi

if [ "$FAIL" = "0" ]; then
  echo "== RESULT: every request answered 200 inside $MEM"
else
  echo "== RESULT: NOT CLEAN inside $MEM (a request did not answer 200, or the container stopped)"
fi
exit "$FAIL"
