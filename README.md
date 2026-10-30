# hdhr-guide

Builds an [XMLTV](https://wiki.xmltv.org/) TV guide from the free guide data that
HDHomeRun tuners get from SiliconDust, and keeps it up to date. Point Jellyfin (or any
other app that reads XMLTV) at the file and your live TV channels get program listings,
no paid guide service needed.

## How it works

Every few hours the script:

1. Asks your HDHomeRun for its device ID and channel lineup.
2. Pages through `api.hdhomerun.com` from now until the guide data runs out (usually
   a couple of days ahead).
3. Writes `guide.xml` with channels, titles, episode info, descriptions, artwork and
   categories (Movie, Sports, News, Kids).

If an update fails, the last good file is kept and it tries again next round.

It's a single Python file using only the standard library, run in the stock
`python:3.12-alpine` image. There's nothing to build.

## Setup

1. Clone the repo and create your settings file:

   ```sh
   git clone https://github.com/jdogskizzle/hdhr-guide.git
   cd hdhr-guide
   cp .env.example .env
   ```

2. Edit `.env`:

   | Setting          | Required | Description |
   |------------------|----------|-------------|
   | `HDHR_HOST`      | yes      | IP address or hostname of your HDHomeRun |
   | `PUID` / `PGID`  | yes      | User and group the container runs as (`id -u`, `id -g`). They need write access to `OUTPUT_DIR`. |
   | `OUTPUT_DIR`     | yes      | Host folder where `guide.xml` is written |
   | `INTERVAL_HOURS` | no       | Hours between refreshes (default `4`) |

3. Start it:

   ```sh
   docker compose up -d
   docker compose logs -f
   ```

   A successful run logs something like
   `wrote 42 channels, 3150 programmes through 2026-10-31 18:00 UTC`.

## Using it with Jellyfin

The easiest setup is to set `OUTPUT_DIR` to a folder Jellyfin can already see, for
example its config folder's `xmltv` subfolder. Then in Jellyfin:

1. Go to **Dashboard → Live TV → TV Guide Data Providers → Add → XMLTV**.
2. Set the file path to where `guide.xml` appears inside the Jellyfin container
   (for example `/config/xmltv/guide.xml`).
3. Map channels if needed. Channel IDs are the HDHomeRun guide numbers (such as `5.1`),
   so they usually match automatically.

## Running without Docker

```sh
HDHR_HOST=192.168.1.50 OUT=./guide.xml python3 guide.py
```

`OUT` sets the output file path (default `/out/guide.xml`, the path inside the container).

## License

[MIT](LICENSE)
