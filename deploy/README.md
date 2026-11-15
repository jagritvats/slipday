# Deploying Slipday

The public instance runs as one container on an arm64 Linux VM behind a shared Traefik edge and Cloudflare.

## How a deploy happens

Every push to `main` runs `.github/workflows/deploy.yml`:

1. builds `Dockerfile` for `linux/arm64` and pushes `ghcr.io/<owner>/slipday:<sha>` and `:main`;
2. copies `deploy/docker-compose.yml` and `deploy/deploy.sh` to `$DEPLOY_PATH/deploy/` on the VM;
3. runs `deploy.sh`, which checks the large grids are present, pulls the image, restarts the service,
   waits for `/api/health` and warns if the app is not on the 80 m grid.

The run is skipped unless the repository variable `DEPLOY_ENABLED` is `true`.

| Setting | Kind | Value |
|---|---|---|
| `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS` | secret | SSH access to the VM |
| `DEPLOY_PORT` | secret, optional | default 22 |
| `DEPLOY_ENABLED` | variable | `true` to deploy |
| `DEPLOY_PATH` | variable, optional | default `/opt/spaceapps/slipday` |
| `SLIPDAY_HOST_RULE` | variable, optional | Traefik rule, default ``Host(`slipday.synpse.app`)``; several hosts are joined with `\|\|`, never commas |

## Shared VM: keep the project name

`docker-compose.yml` sets `name: slipday`, and `deploy.sh` does not use `--remove-orphans`.
Keep both. Without the name, Compose calls the project `deploy` after its folder, which other
stacks on the VM share. The first deploy on 15 Nov 2026 had no name, and `--remove-orphans`
deleted the personal site's container (`jagritvats-site`, down about 10 minutes). Rule for every
stack on that VM: its own project name, no VM-wide `docker image prune -a`, and only remove your
own app's old image tags.

## The large grids (once per VM)

The 80 m grid, the 20 m crop and the 5 m site models are over GitHub's file limit, so they are not in the
image. Build them with the scripts (`scripts/fetch_grid80.py`, `scripts/fetch_ldem20_tiles.py`,
`scripts/finer_map_store.py`, `scripts/prepare_dem5.py`) and copy them to the VM:

```
/opt/spaceapps/slipday/data-large/
  dem/ldem_80s_80m_f32.npy
  dem20/   (dems.json, ldem_pole_20m_f32.npy, scatter20_el_i16.npy, scatter20_done.npy)
  dem5/    (site01/, site07/: dems.json and the 5 m .npy)
  horizon_cache/   (optional seed; the app adds to it)
```

From a machine that has them, without rsync:

```
tar -C data -cf - dem/ldem_80s_80m_f32.npy dem20 dem5 horizon_cache \
  | ssh <user>@<host> "mkdir -p /opt/spaceapps/slipday/data-large && tar -C /opt/spaceapps/slipday/data-large -xf -"
```

## By hand on the VM

```
cd /opt/spaceapps/slipday
SLIPDAY_IMAGE=ghcr.io/<owner>/slipday:main bash deploy/deploy.sh
docker compose -f deploy/docker-compose.yml logs -f
curl -s http://127.0.0.1:8100/api/health
```
