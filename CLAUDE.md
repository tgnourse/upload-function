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
| `ambient-weather` (entry `upload_function`) | `python312` | Active, deployed 10/18/2026 | Cloud Scheduler jobs `tommy_ambient_weather`, `garrett_ambient_weather`, `nick_ambient_weather`, each `*/5 * * * *` | `temperatures` / `uploadfunction` | Pulls Ambient Weather API (`/v1/devices`) for an account, maps MAC → sensor name |
| `signals-thermometer` (entry `upload_function`) | `python37` (retired runtime) | Deployed, but Scheduler job `tommy_thermoworks_signals` **paused since Apr 2024** | Cloud Scheduler | `temperatures` / `signals` | Logs into Thermoworks "smoke-cloud" Firebase, reads the last 50 `SignalTemps/<device_id>` probe readings |
| `temp-led` (entry `get_function`) | `python312` | Active, deployed 10/19/2026 | Arduino polls every 60 s | reads `temperatures` / `wemos` | `?id=N` → color as a Python dict string (`{'red': …, 'green': …, 'blue': …}`, or a list of 7 for the 7-LED config). Configs are hard coded in `main.py`; e.g. `id=1` uses the LAST temperature of `original_sensor_id` `24:7D:4D:A3:64:EE_1` (<66 °F blue, >74 °F red, else green). Configured IDs: `1`, `3`, `4`; `id=2` (PurpleAir air quality) was removed 10/19/2026 after PurpleAir retired its old `/json` endpoint |
| `wspr` | Python (`wspr/main.py`) | **Turned down 5/27/2020** | Rob's wsprdaemon (`logs.wsprdaemon.org` pointed here) | `wspr` / `wspr` | WSPR spots: GET single spot or POST multi-upload (`allmept` file + `call` + `grid`) mirroring wsprnet.org's API |
| `upload_radio` | Node.js | **Turned down 5/27/2020** | Rob's KiwiSDR noise logger | `radio` / `radio` | Atmospheric noise: `fft_level`, `rms_level`, `site`, `band`, `receiver`, `maidenhead`, `timestamp_ms` |

### Request formats

```bash
# upload (Wemos) — query params mirror the Dweet-style GET the Lua code builds
curl "https://us-central1-iot-data-storage.cloudfunctions.net/upload?temperature=81.3&hum=44.7&heap=33752&ip=192.168.1.132&ssid=Blinky&sensor_id=test"

# ambient-weather — keys are passed as query params by Cloud Scheduler
curl "https://us-central1-iot-data-storage.cloudfunctions.net/ambient-weather?apiKey=$AMBIENT_API_KEY&applicationKey=$AMBIENT_APPLICATION_KEY"

# signals-thermometer
curl "https://us-central1-iot-data-storage.cloudfunctions.net/signals-thermometer?email=$THERMOWORKS_EMAIL&password=$THERMOWORKS_PASSWORD&device_id=84:0d:8e:23:c7:9e&device_name=tgnourse_signals"

# temp-led
curl "https://us-central1-iot-data-storage.cloudfunctions.net/temp-led?id=1"

# wspr single spot (historical)
curl "https://us-central1-iot-data-storage.cloudfunctions.net/wspr?rcall=KPH&rgrid=CM88mc&rqrg=18.106100&date=200119&time=2002&sig=-21&dt=0.2&drift=0&tqrg=18.106102&tcall=AC8MO&tgrid=EN82&dbm=27&version=WD-2.6f&mode=2"

# upload_radio (historical)
curl "https://us-central1-iot-data-storage.cloudfunctions.net/upload_radio?fft_level=-160.5&rms_level=-170.3&site=KPH&band=630&receiver=KiwiSDR15&timestamp_ms=1557379274758"
```

Note: `ambient-weather` and `signals-thermometer` receive credentials in the URL query string (visible
in Scheduler config and logs). Prefer moving them to function env vars / Secret Manager when touching
that code.

### Environment variables on the functions

| Var | Used by | Notes |
|---|---|---|
| `influxdb_host`, `influxdb_port`, `influxdb_user`, `influxdb_password`, `influxdb_database` | all | lowercase names — that's what the code reads |
| `sensor_mapping` | `upload`, `ambient-weather` | JSON. `upload`: `{"tgnourse1":"under_front_stairs","tgnourse4":"master_bedroom","tgnourse5":"maintenance_closet","tgnourse6":"tommy_closet"}` (Sept 2018). `ambient-weather`: `{"A4:CF:12:A0:32:1C":"tgnourse_house"}`; signals: `{"84:0d:8e:23:c7:9e":"tgnourse_signals"}` |
| `api_key` (Firebase web key for smoke-cloud) | `signals-thermometer` | Was a hard-coded default in 2020 |

Mapped devices: when a `sensor_mapping` entry exists, `sensor_id` is the friendly name and the raw ID is
kept in `original_sensor_id`. `ambient-weather` appends a suffix (`_outdoor`, `_indoor`, `_1`…`_7`) to both,
so mapping a MAC to a name that already ends in `_indoor` produces `..._indoor_indoor` (this is happening
for one of Tommy's devices in production).

Python functions must read these with `os.environ`. `request.environ` only carried them on the retired
`python37` runtime; every function except `signals-thermometer` uses `os.environ`.

## Local development

All functions are Python. `ambient-weather`, `signals-thermometer` and `temp-led` have a `__main__` dev
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
DELETE FROM spot WHERE tcall = 'TCALL'                                    -- wspr tests (retired)
```

## Deploying

All functions are 1st gen. Until Oct 2026 they were deployed through the GCP console from the Cloud
Source Repositories mirror. `ambient-weather` (10/18/2026) and `upload` (10/19/2026, with
`--source=upload`) have since been deployed from the CLI with:

```bash
gcloud functions deploy ambient-weather --project=iot-data-storage --region=us-central1 \
  --no-gen2 --runtime=python312 --entry-point=upload_function --trigger-http \
  --source=ambient-weather
```

- Use `--no-gen2`; current gcloud defaults to 2nd gen.
- **Don't pass `--set-env-vars` / `--env-vars-file`**: they replace all existing env vars, including
  `sensor_mapping` and the passwords. Omitting them keeps what's deployed. Leave IAM flags off too.
- The retired `python37` runtime can't be redeployed. Upgrading `signals-thermometer` means switching to
  `python312`, and to `os.environ` first.
- Always deploy from a function's directory, never the repo root. `.gcloudignore` excludes `.env` and
  `SECRETS_INVENTORY.md` as a backstop.
- Inspect without leaking secrets: `gcloud functions describe` prints env var **values**, and
  `gcloud scheduler jobs list --format=json` prints URLs with API keys and passwords in the query string.
  Filter those out before showing output.
- Rollback: redeploy the previous commit with the same command (old runtime versions aren't available).

Always ask Tommy before deploying; these functions feed live dashboards.

## Data sources reference

- **Ambient Weather**: `GET https://api.ambientweather.net/v1/devices?applicationKey=...&apiKey=...`.
  There are separate `apiKey`s for Tommy, Garrett and Nick; the `applicationKey` for Nick's station
  was changed on 9/6/2020. Tommy's account (as of Oct 2026): WS-2902A `A4:CF:12:A0:32:1C` ("El Prado",
  outdoor), indoor hub `24:7D:4D:A3:64:EE` ("El Prado Indoor", channels 1–3 and 5–7),
  `24:7D:4D:A3:64:8D` ("Travel Station", channels 1–2) and `FC:F5:C4:98:51:EB` ("Half Moon Bay",
  indoor only; no data since Nov 2024).
- **Thermoworks Signals** (Firebase project `smoke-cloud`): sign in with
  `POST https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=<api_key>` →
  `idToken`; then `https://smoke-cloud.firebaseio.com/signals/<mac>/names.json?auth=<idToken>` for probe
  names and `.../SignalTemps/<mac>/.json?orderBy="$key"&limitToLast=1&auth=<idToken>` for latest temps.
  Probes p1–p4 (`Oven`, `CH 2`–`CH 4`); `"---"` means unplugged. Tokens expire in 3600 s.
- **WSPR** upload formats come from Rob's wsprdaemon (`wsprnet.org/post?function=wspr&...` and
  `meptspots.php` multipart).
