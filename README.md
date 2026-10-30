# Realmwatch

A self-hosted Valheim dashboard with server status, character history and a
read-only portal atlas for each world. Python standard library backend,
plain JavaScript frontend, and a small Docker web container.

## AI-generated origin and community contributions

Realmwatch's initial code, documentation and placeholder graphics were
AI-generated using OpenAI Codex, under human direction. This is stated openly
so users and contributors can assess the project with that context.

**Human-created contributions are warmly welcomed**, especially original
illustrations, icons, biome graphics, typography and UI design. The current
map artwork is a starting point. Improvements to code, accessibility, tests,
documentation and translations are equally welcome. You do not need to use
AI to contribute.

See [CONTRIBUTING.md](CONTRIBUTING.md) for artwork requirements, attribution
and how to propose a change.

## Features

- Discover Valheim containers using the community Valheim server image.
- Live server queries, online character names where available, and retained
  login/logout history per realm. Uncertain events are labelled explicitly.
- Read portal tags, XYZ positions and saved connections from committed
  Valheim 1.0 chunked world saves, without changing game saves or backups.
- Per-world portal registry, linked/unpaired/unresolved status, exact-tag
  matching information, search, selectable endpoints and connection lines.
- Circular world view with a visible world edge, distance rings, approximate
  biome guides, illustrated Deep North/Ashlands caps, and zoom controls.
- No generated landmasses, coastlines, seed-derived terrain or unexplored
  geography. Polar caps and radial colours are illustrations only.
- Authenticated reverse-proxy integration using a shared upstream secret.
  The web container has no Docker socket or game-world mounts.

## Requirements

Linux, Docker with Compose, Python 3.11+ on the game host, and Valheim containers
based on `ghcr.io/community-valheim-tools/valheim-server`. The collector uses
Docker inspection, retained JSON logs and the image's `valheim-status` command.
It needs host Docker administration privileges and read access to world saves.
The dashboard itself runs without privileges and only reads published JSON.

The portal reader supports chunked save versions 40–42 in
`/config/worlds_local/WORLD_NAME`. Unsupported, legacy, mod-altered or future
formats are reported unavailable rather than guessed. This is an unofficial,
community tool, not affiliated with Iron Gate.

## Install on the game host

Place this project in `/opt/realmwatch`, then run:

```sh
cd /opt/realmwatch
sudo python3 scripts/init.py
sudo cp realmwatch.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now realmwatch
sudo docker compose up -d --build
curl http://127.0.0.1:8088/healthz
```

The dashboard backend defaults to **127.0.0.1:8088** and requires the upstream
secret for all pages/API routes except `/healthz`. An initial HTTP503 is normal
until the first collector scan completes. Configure an authenticated HTTPS
reverse proxy before accessing the dashboard; see [gateway setup](gateway/README.md).
Do not expose the backend directly to the Internet. The shared header authenticates
the gateway, not individual viewers; it must never be embedded in frontend code.

The collector scans every 15 seconds. It writes `data/history.sqlite3` and
atomically publishes `data/public/status.json`. Portal data changes after the
game saves, not immediately after building/renaming a portal. Player-history
and dashboard time displays currently use Europe/London.

## Operations

```sh
systemctl status realmwatch
journalctl -u realmwatch -n 30
docker compose logs --tail 30
```

Preserve `data/` and `secrets/`. Back up a live history database with SQLite's
backup API, not by copying the database alone while writes are active. Back up
source/configuration and retain the old dashboard image before upgrading.
A rollback should restore source/image while retaining current player history.
This application never needs a game restart or a game-world restore.

To remove, stop/disable `realmwatch.service` and run `docker compose down` in this
project. Preserve data if you want history. Game containers are independent.

## Limits and interpretation

Saved links are not live teleportability checks. Matching tags alone do not
prove a connection. Missing or ambiguous partners are unresolved. Blank tags
are preserved. Portal identifiers are derived from prefab/position and can
change when an endpoint moves. [Portal format and privacy notes](PORTALS.md).

The history can only recover retained logs. Missing logout events are marked
approximate, and simultaneous ambiguous joins are not assigned guessed identities.
Steam identifiers and raw game logs are not included in dashboard JSON. Character
names, portal tags and positions remain private game data: restrict viewers.

## Development

```sh
python3 -m unittest -v
python3 -m compileall -q collector.py portals.py server.py
docker build -t realmwatch:test .
```

The Docker build validates JavaScript syntax. CI runs unit tests and builds
the dashboard. There are no third-party Python dependencies.

## Licence

Realmwatch is released under the [MIT licence](LICENSE). You may use, modify
and redistribute it, including commercially, provided the copyright and
permission notice are retained. It is provided without warranty. Third-party
trademarks and game assets are not relicensed by this project.
