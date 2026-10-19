# upload-function — Cloud Functions for the IoT data platform

HTTP Cloud Functions in GCP project `iot-data-storage` (region `us-central1`) that receive or pull
sensor data and write it into InfluxDB 1.x (`influxdb-2-vm`, `35.238.159.210:8086`, self-signed HTTPS).
Grafana at grafana.int8.com reads the results. Repo: `github.com/tgnourse/upload-function`, mirrored
into Cloud Source Repositories as `upload-function` (the GitHub repo became the source on 9/20/2018).
Console deploys before Oct 2026 pulled code from that mirror's `master`.

> Reconstructed from Tommy's project log. Function runtimes, entry points, env var names, Scheduler
> jobs and deploy details were checked against GCP on 10/18/2026; the rest may have drifted — check
> the code and the GCP console before relying on it. See the `iot-platform` CLAUDE.md for the InfluxDB
> and Grafana side.

## Secrets

Credentials are passed to functions as **environment variables set on the deployed function** (and
inline env vars when running locally). Older code had fallback defaults hard-coded in `main.py`
(`if not influx_host: ...`) — if you find any, replace them with env-var reads and fail loudly when
missing. Never commit `.env`, API keys, or passwords. Don't echo secrets in command output you show.

## Functions

Base URL: `https://us-central1-iot-data-storage.cloudfunctions.net/<name>`

| Function | Runtime | Status | Trigger | Writes to (db / user) | What it does |
|---|---|---|---|---|---|
| `upload` (`upload/main.py`, entry `upload_function`) | `python312` (ported from Node.js `index.js`) | Active, deployed 10/19/2026 | Wemos sensors, GET every 300 s | `temperatures` / `uploadfunction` | Stores `temperature`, `hum`, `heap`, `ip`, `ssid`, `sensor_id`; renames IDs via `sensor_mapping` |
| `ambient-weather` (entry `upload_function`) | `python312`, **Cloud Run function (2nd gen)** | Active, upgraded 10/19/2026 | Cloud Scheduler jobs `tommy_ambient_weather`, `garrett_ambient_weather`, `nick_ambient_weather`, each `*/5 * * * *` | `temperatures` / `uploadfunction` | Pulls Ambient Weather API (`/v1/devices`) for an account, maps MAC → sensor name |
| `fireboard` (entry `upload_function`) | `python312`, Cloud Run function (2nd gen), **private** | Active, deployed 10/19/2026 | Cloud Scheduler job `tommy_fireboard`, `* * * * *`, OIDC as `fireboard-scheduler@` | `temperatures` / `uploadfunction` | One `devices.json` call per run → `environment_sensor` points `fireboard_<title>_<label>`; Beacon humidity (`degreetype` 3) + battery/signal on channel 1. Devices (Oct 2026): Glycol Chiller, Indoor Wine Bottle, Unused in Garage (Beacons), Portable (FireBoard 2), Yoder (smoker, idle) |
| `tilt` (entry `upload_function`) | `python312`, Cloud Run function (2nd gen), public + `?key=` | Active, deployed 10/19/2026 | Tilt Pico custom cloud URL (form-encoded POST) | `temperatures` / `uploadfunction`, measurement **`tilt`** | Tilt Pro readings → `temperature`, `specific_gravity`, `brix`; tags `sensor_id` (`tilt_<color>`), `color`, `beer` |
| `temp-led` (entry `get_function`) | `python312` | Active, deployed 10/19/2026 | Arduino polls every 60 s | reads `temperatures` / `wemos` | `?id=N` → color as a Python dict string (`{'red': …, 'green': …, 'blue': …}`, or a list of 7 for the 7-LED config). Configs are hard coded in `main.py`; e.g. `id=1` uses the LAST temperature of `original_sensor_id` `24:7D:4D:A3:64:EE_1` (<66 °F blue, >74 °F red, else green). Configured IDs: `1`, `3`, `4`; `id=2` (PurpleAir air quality) was removed 10/19/2026 after PurpleAir retired its old `/json` endpoint |
| `wspr` | Python (`wspr/main.py`) | **Turned down 5/27/2020** | Rob's wsprdaemon (`logs.wsprdaemon.org` pointed here) | `wspr` / `wspr` | WSPR spots: GET single spot or POST multi-upload (`allmept` file + `call` + `grid`) mirroring wsprnet.org's API |
| `upload_radio` | Node.js | **Turned down 5/27/2020** | Rob's KiwiSDR noise logger | `radio` / `radio` | Atmospheric noise: `fft_level`, `rms_level`, `site`, `band`, `receiver`, `maidenhead`, `timestamp_ms` |

### Request formats

```bash
# upload (Wemos) — query params mirror the Dweet-style GET the Lua code builds
curl "https://us-central1-iot-data-storage.cloudfunctions.net/upload?temperature=81.3&hum=44.7&heap=33752&ip=192.168.1.132&ssid=Blinky&sensor_id=test"

# ambient-weather — keys are passed as query params by Cloud Scheduler
curl "https://us-central1-iot-data-storage.cloudfunctions.net/ambient-weather?apiKey=$AMBIENT_API_KEY&applicationKey=$AMBIENT_APPLICATION_KEY"

# temp-led
curl "https://us-central1-iot-data-storage.cloudfunctions.net/temp-led?id=1"

# wspr single spot (historical)
curl "https://us-central1-iot-data-storage.cloudfunctions.net/wspr?rcall=KPH&rgrid=CM88mc&rqrg=18.106100&date=200119&time=2002&sig=-21&dt=0.2&drift=0&tqrg=18.106102&tcall=AC8MO&tgrid=EN82&dbm=27&version=WD-2.6f&mode=2"

# upload_radio (historical)
curl "https://us-central1-iot-data-storage.cloudfunctions.net/upload_radio?fft_level=-160.5&rms_level=-170.3&site=KPH&band=630&receiver=KiwiSDR15&timestamp_ms=1557379274758"
```

Note: `ambient-weather` receives credentials in the URL query string (visible
in Scheduler config and logs). Prefer moving them to function env vars / Secret Manager when touching
that code.

### Environment variables on the functions

| Var | Used by | Notes |
|---|---|---|
| `influxdb_host`, `influxdb_port`, `influxdb_user`, `influxdb_password`, `influxdb_database` | all | lowercase names — that's what the code reads |
| `fireboard_token` | `fireboard` | From Secret Manager secret `fireboard-token`. Local copy: `FIREBOARD_TOKEN` in `.env` |
| `sensor_id_prefix` | `fireboard`, `tilt` | Optional, defaults `fireboard` / `tilt`; use `test_fireboard` / `test_tilt` for local tests |
| `tilt_key` | `tilt` | From Secret Manager secret `tilt-key`; the Pico must send it as `?key=`. Full URL in `.env` as `TILT_CLOUD_URL` |
| `sensor_mapping` | `upload`, `ambient-weather` | JSON. `upload`: `{"tgnourse1":"under_front_stairs","tgnourse4":"master_bedroom","tgnourse5":"maintenance_closet","tgnourse6":"tommy_closet"}` (Sept 2018). `ambient-weather`: `{"A4:CF:12:A0:32:1C":"tgnourse_house"}` |

Mapped devices: when a `sensor_mapping` entry exists, `sensor_id` is the friendly name and the raw ID is
kept in `original_sensor_id`. `ambient-weather` appends a suffix (`_outdoor`, `_indoor`, `_1`…`_7`) to both,
so mapping a MAC to a name that already ends in `_indoor` produces `..._indoor_indoor` (this is happening
for one of Tommy's devices in production).

Functions must read these with `os.environ`; `request.environ` only carried them on the retired `python37`
runtime.

## Local development

All functions are Python. `ambient-weather` and `temp-led` have a `__main__` dev
server on `localhost:8000`; `upload` doesn't, so run it with `functions-framework --target=upload_function`.

```bash
cd ambient-weather
influxdb_host=$INFLUXDB_HOST influxdb_port=8086 influxdb_user=uploadfunction \
influxdb_password=$INFLUXDB_UPLOADFUNCTION_PASSWORD influxdb_database=temperatures \
sensor_mapping='{"A4:CF:12:A0:32:1C":"tgnourse_house"}' python3 main.py

curl "http://localhost:8000/?apiKey=$AMBIENT_API_KEY&applicationKey=$AMBIENT_APPLICATION_KEY"
```

To match the deployed runtime, run it under Python 3.12 with
`functions-framework --target=upload_function --port=8089` instead of `python3 main.py`.

When testing `ambient-weather` against the real database, set `sensor_mapping` to map **every** MAC on
the account to a `test_ambient_N` name. The test points then land in separate series (they still carry
the real `original_sensor_id`, `mac` and `location` tags, so filter on `sensor_id`, not those).

For `upload`, test with `sensor_id=test` and an empty `sensor_mapping`; a request with `pressure` also
creates a `test_pressure` series. The retired `radio/` function is still Node.js.

Clean up test data afterwards (confirm first; the `claude` user can DELETE on `temperatures`). Check the
match with `SHOW TAG VALUES FROM environment_sensor WITH KEY = sensor_id WHERE sensor_id =~ /^test_/`
before deleting, and never delete by `mac` or `original_sensor_id` — those match production data too.

```sql
DELETE FROM environment_sensor WHERE "sensor_id" =~ /^test(_pressure)?$/ -- upload tests
DELETE FROM environment_sensor WHERE "sensor_id" =~ /^test_ambient_/     -- ambient-weather tests
DELETE FROM environment_sensor WHERE "sensor_id" =~ /^test_fireboard_/   -- fireboard tests
DELETE FROM tilt WHERE "sensor_id" =~ /^test_tilt_/                      -- tilt tests
DELETE FROM spot WHERE tcall = 'TCALL'                                    -- wspr tests (retired)
```

## Deploying

Until Oct 2026 functions were deployed through the GCP console from the Cloud Source Repositories
mirror. They're now deployed from the CLI, from each function's directory.

**`upload` and `temp-led` must stay 1st gen** (or sit behind something that accepts plain HTTP). The
Wemos sensors (`~/Projects/wemos`, `conn:connect(80, HOST)`) and the LED Arduino
(`~/Projects/arduino/temp-led`, `client.connect(host, 80)`) send plain HTTP to port 80. 1st gen
functions are `SECURE_OPTIONAL` and serve it; 2nd gen returns `302` to `https://`, which the devices
don't follow. Verified with a throwaway 2nd gen function on 10/19/2026.

```bash
gcloud functions deploy upload --project=iot-data-storage --region=us-central1 \
  --no-gen2 --runtime=python312 --entry-point=upload_function --trigger-http \
  --source=upload
# temp-led: --entry-point=get_function --source=temp-led
```

- Use `--no-gen2`; current gcloud defaults to 2nd gen.

**`ambient-weather` is a Cloud Run function (2nd gen).** It was upgraded on 10/19/2026 with
`gcloud functions upgrade ambient-weather --setup-config` → `--redirect-traffic` → `--commit`. The commit
detaches it from the Cloud Functions API, so it's now a Cloud Run service: `gcloud functions list` /
`describe` / `logs read` don't see it. The `cloudfunctions.net` URL (which Cloud Scheduler calls over
HTTPS) still works, and it's also at `https://ambient-weather-bgdddlrosa-uc.a.run.app`.

```bash
# Deploy (not yet exercised since the upgrade; check env vars are kept afterwards)
gcloud run deploy ambient-weather --project=iot-data-storage --region=us-central1 \
  --source=ambient-weather --function=upload_function --base-image=python312

# Logs (don't print httpRequest.requestUrl, it has the API keys)
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="ambient-weather"' \
  --project=iot-data-storage --limit=20 --format='value(timestamp,httpRequest.status,textPayload)'
```

- **Don't pass `--set-env-vars` / `--env-vars-file`**: they replace all existing env vars, including
  `sensor_mapping` and the passwords. Omitting them keeps what's deployed. Leave IAM flags off too.
- Always deploy from a function's directory, never the repo root. `.gcloudignore` excludes `.env` and
  `SECRETS_INVENTORY.md` as a backstop.
- Inspect without leaking secrets: `gcloud functions describe` and `gcloud run services describe` print
  env var **values**, and
  `gcloud scheduler jobs list --format=json` prints URLs with API keys and passwords in the query string.
  Filter those out before showing output.
- Rollback: redeploy the previous commit with the same command (old runtime versions aren't available).

**`fireboard` is private and uses Secret Manager** (the pattern to follow for new functions). Runtime
service account `fireboard-fn@` can read secrets `fireboard-token` and `influxdb-uploadfunction-password`;
`fireboard-scheduler@` has `roles/run.invoker` on the service and is the Scheduler job's OIDC identity.
Anonymous calls get a 403. Unlike the others, redeploys must repeat the env vars and secrets:

```bash
gcloud functions deploy fireboard --project=iot-data-storage --region=us-central1 \
  --gen2 --runtime=python312 --entry-point=upload_function --trigger-http --no-allow-unauthenticated \
  --source=fireboard --service-account=fireboard-fn@iot-data-storage.iam.gserviceaccount.com \
  --set-env-vars=influxdb_host=35.238.159.210,influxdb_port=8086,influxdb_user=uploadfunction,influxdb_database=temperatures \
  --set-secrets=fireboard_token=fireboard-token:latest,influxdb_password=influxdb-uploadfunction-password:latest
```

To rotate the FireBoard token or InfluxDB password, add a new secret version
(`gcloud secrets versions add <secret> --data-file=-`) and redeploy so the function picks up `latest`.

**`tilt` is public but checks a shared key** (`?key=` against secret `tilt-key`, runtime SA `tilt-fn@`),
because the Tilt Pico can't send auth headers. Never log `request.args`. Rotating the key means
updating the custom cloud URL in the Tilt app too. Redeploy with:

```bash
gcloud functions deploy tilt --project=iot-data-storage --region=us-central1 \
  --gen2 --runtime=python312 --entry-point=upload_function --trigger-http --allow-unauthenticated \
  --source=tilt --service-account=tilt-fn@iot-data-storage.iam.gserviceaccount.com \
  --set-env-vars=influxdb_host=35.238.159.210,influxdb_port=8086,influxdb_user=uploadfunction,influxdb_database=temperatures \
  --set-secrets=tilt_key=tilt-key:latest,influxdb_password=influxdb-uploadfunction-password:latest
```

Always ask Tommy before deploying; these functions feed live dashboards.

## Data sources reference

- **Ambient Weather**: `GET https://api.ambientweather.net/v1/devices?applicationKey=...&apiKey=...`.
  There are separate `apiKey`s for Tommy, Garrett and Nick; the `applicationKey` for Nick's station
  was changed on 9/6/2020. Tommy's account (as of Oct 2026): WS-2902A `A4:CF:12:A0:32:1C` ("El Prado",
  outdoor), indoor hub `24:7D:4D:A3:64:EE` ("El Prado Indoor", channels 1–3 and 5–7),
  `24:7D:4D:A3:64:8D` ("Travel Station", channels 1–2) and `FC:F5:C4:98:51:EB` ("Half Moon Bay",
  indoor only; no data since Nov 2024).
- **Thermoworks Signals**: the `signals-thermometer` function and its Scheduler job
  `tommy_thermoworks_signals` were deleted on 10/19/2026 (thermometer no longer used). Code is in git history.
- **FireBoard** (https://docs.fireboard.io/app/app-api/): token from `POST /api/rest-auth/login/`, sent as
  `Authorization: Token <key>`; `User-Agent` required. **17 calls per user per 5 minutes** (the FireBoard
  app shares this budget; going over blocks for ~5 minutes). `latest_temps` only includes readings < 60 s
  old. `degreetype`: 1 = °C, 2 = °F, 3 = humidity % (undocumented). Battery is `device_log.vBattPer`
  (0–1); signal is `device_log.signallevel`. Beacons (`FBRFS`) relay through the Portable FireBoard 2.
- **Tilt Pico** (Pico W bridge for Tilt hydrometers; firmware https://github.com/baronbrew/TiltPico):
  posts `application/x-www-form-urlencoded` with `Timepoint` (spreadsheet date, local time), `Temp`
  (°F), `SG` (at 60 °F; Tilt Pros have 4 decimals), `Beer`, `Color`, `Comment`. It has a default cloud URL
  (Google Sheets) plus two custom ones; ours is in a custom slot. Also serves JSON locally at
  `tiltpico.local` (not reachable from Tommy's Mac on 10/19/2026).
- **WSPR** upload formats come from Rob's wsprdaemon (`wsprnet.org/post?function=wspr&...` and
  `meptspots.php` multipart).
