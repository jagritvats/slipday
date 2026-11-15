#!/usr/bin/env bash
# Runs on the VM (called by .github/workflows/deploy.yml, or by hand):
#   SLIPDAY_IMAGE=ghcr.io/jagritvats/slipday:<sha> bash deploy/deploy.sh
# Checks the large data is in place, pulls the image, restarts the service, waits for /api/health and
# checks the app is on the 80 m grid, then removes older Slipday images.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

IMAGE="${SLIPDAY_IMAGE:-ghcr.io/jagritvats/slipday:main}"
DATA="${SLIPDAY_DATA:-/opt/spaceapps/slipday/data-large}"
PORT="${SLIPDAY_LOCAL_PORT:-8100}"

missing=0
for p in "$DATA/dem/ldem_80s_80m_f32.npy" "$DATA/dem20/dems.json" "$DATA/dem20/ldem_pole_20m_f32.npy" \
         "$DATA/dem5/site01/dems.json" "$DATA/dem5/site07/dems.json"; do
  if [[ ! -f "$p" ]]; then
    echo "Missing $p" >&2
    missing=1
  fi
done
if [[ "$missing" -eq 1 ]]; then
  echo "Copy the large grids to $DATA first (see deploy/README.md)." >&2
  exit 1
fi
mkdir -p "$DATA/horizon_cache"

docker network inspect "${TRAEFIK_NETWORK:-synapse-edge}" >/dev/null

if [[ -n "${GHCR_TOKEN:-}" ]]; then
  printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:?GHCR_USER is required with GHCR_TOKEN}" --password-stdin
fi

{
  echo "SLIPDAY_IMAGE=$IMAGE"
  echo "SLIPDAY_DATA=$DATA"
  echo "SLIPDAY_LOCAL_PORT=$PORT"
  [[ -n "${SLIPDAY_HOST_RULE:-}" ]] && echo "SLIPDAY_HOST_RULE=$SLIPDAY_HOST_RULE"
  [[ -n "${SLIPDAY_MEM_LIMIT:-}" ]] && echo "SLIPDAY_MEM_LIMIT=$SLIPDAY_MEM_LIMIT"
  true
} > .env

# A container called "slipday" left over from before the project had its own name would block the new one.
old_project="$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' slipday 2>/dev/null || true)"
if [[ -n "$old_project" && "$old_project" != "slipday" ]]; then
  echo "Removing the old slipday container from compose project '$old_project'."
  docker rm -f slipday >/dev/null
fi

# No --remove-orphans: the VM is shared, and this stack owns exactly one service.
docker compose pull
docker compose up -d

echo "Waiting for /api/health ..."
health=""
for _ in $(seq 1 60); do
  if health="$(curl -fsS --max-time 5 "http://127.0.0.1:${PORT}/api/health" 2>/dev/null)"; then
    break
  fi
  health=""
  sleep 3
done
if [[ -z "$health" ]]; then
  echo "Slipday did not answer /api/health in 3 minutes." >&2
  docker compose ps >&2
  docker compose logs --tail 120 >&2
  exit 1
fi
echo "$health" | head -c 600; echo
if ! grep -q "80 m/px" <<<"$health"; then
  echo "::warning::Slipday is up but not on the 80 m grid; the submission examples need it." >&2
fi

# Keep the running image and :main; drop older Slipday tags so the disk does not fill up.
repo="${IMAGE%:*}"
docker images "$repo" --format '{{.Repository}}:{{.Tag}}' \
  | grep -v -x -e "$IMAGE" -e "$repo:main" \
  | xargs -r docker rmi >/dev/null 2>&1 || true
docker image prune -f >/dev/null || true

docker compose ps
