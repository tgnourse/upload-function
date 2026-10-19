# upload-function
A collection of Google Cloud Functions for getting environmental and radio data into an InfluxDB instance (and, in
one case, back out again).

| Directory | Language | Entry point | What it does |
|---|---|---|---|
| `upload/` | Python | `upload_function` | Receives temperature/humidity/pressure readings from sensors via HTTP. |
| `radio/` | Node.js | `uploadFunction` | **Retired (May 2020).** Received atmospheric noise levels from radio receivers via HTTP. |
| `wspr/` | Python | `upload_function` | **Retired (May 2020).** Received [WSPR](https://en.wikipedia.org/wiki/WSPR_(amateur_radio_software)) spots in the same format as [WSPRnet](http://wsprnet.org/). |
| `ambient-weather/` | Python | `upload_function` | Pulls the latest readings from the [Ambient Weather API](https://www.ambientweather.com/api.html) for personal weather stations. |
| `fireboard/` | Python | `upload_function` | Pulls the latest probe, ambient and humidity readings from the [FireBoard API](https://docs.fireboard.io/app/app-api/) every minute. |
| `temp-led/` | Python | `get_function` | Reads the latest temperature for a sensor and returns an RGB color for an LED indicator. |

## Configuration
Every function reads the InfluxDB connection details from environment variables:
* `influxdb_user`: The user. For the upload functions it only needs `WRITE` access to the DB; `temp-led` needs `READ`.
* `influxdb_password`: The user's password.
* `influxdb_host`: Host IP or domain. All functions connect over `https` and **do not verify the certificate**, since
  the InfluxDB instance uses a self-signed cert.
* `influxdb_port`: The port.
* `influxdb_database`: The database name.

Some functions take additional environment variables:
* `sensor_mapping` (`upload`, `ambient-weather`): A JSON object mapping a raw sensor ID to a friendlier name, which is
  written as the `sensor_id` tag (the raw ID is kept in `original_sensor_id`). See `upload/sensor_mapping.json` and
  `ambient-weather/sensor_mapping.json` for the current mappings; these files are just a record of what is configured
  in production, the functions don't read them directly.

## Deploying
Each directory is deployed separately in project `iot-data-storage`, region `us-central1`, on `python312`. All of
them are reached at `https://us-central1-iot-data-storage.cloudfunctions.net/<name>`.

`upload` and `temp-led` are **1st gen** Cloud Functions, because the Wemos sensors and the LED Arduino call them over
plain HTTP, and 2nd gen redirects HTTP to HTTPS (which the devices can't follow). Deploy them with:
```shell
gcloud functions deploy upload --project=iot-data-storage --region=us-central1 \
    --no-gen2 --runtime=python312 --entry-point=upload_function --trigger-http \
    --source=upload
```
(`temp-led`: `--entry-point=get_function --source=temp-led`.)

`ambient-weather` was upgraded to a Cloud Run function (2nd gen) in Oct 2026 and is now managed as a Cloud Run
service, so it no longer appears in `gcloud functions list`. Deploy it with:
```shell
gcloud run deploy ambient-weather --project=iot-data-storage --region=us-central1 \
    --source=ambient-weather --function=upload_function --base-image=python312
```

`fireboard` is a private 2nd gen function (Cloud Scheduler calls it with an OIDC token) whose FireBoard token and
InfluxDB password come from Secret Manager. Its full deploy command, including the env vars and secrets, is:
```shell
gcloud functions deploy fireboard --project=iot-data-storage --region=us-central1 \
    --gen2 --runtime=python312 --entry-point=upload_function --trigger-http --no-allow-unauthenticated \
    --source=fireboard --service-account=fireboard-fn@iot-data-storage.iam.gserviceaccount.com \
    --set-env-vars=influxdb_host=35.238.159.210,influxdb_port=8086,influxdb_user=uploadfunction,influxdb_database=temperatures \
    --set-secrets=fireboard_token=fireboard-token:latest,influxdb_password=influxdb-uploadfunction-password:latest
```

* Don't pass `--set-env-vars` or `--env-vars-file` unless you mean to replace **all** of the function's environment
  variables; leaving them out keeps the existing ones.

### Retired functions
`radio/` (`upload_radio`) and `wspr/` were turned down in May 2020. Their docs below are kept for reference.
`signals-thermometer` (ThermoWorks Signals via Firebase) was deleted in Oct 2026; its code is in git history.

## Functions

### Environmental upload (`upload/`)
Writes to the `environment_sensor` measurement.

```shell
curl http://[your_cloud_function_subdomain].cloudfunctions.net/upload\
    \?temperature\=81.340352483406\
    \&hum\=44.689097428855\
    \&heap\=33752\
    \&ip\=192.168.1.132\
    \&ssid\=SSID\
    \&sensor_id\=Sensor1
```

* `temperature` (°F), `hum` (%), `heap` (bytes), `ip`, `ssid`, `sensor_id`.
* Optional `pressure` (inHg) and `pressure_temperature` (°F). When present, a second point is written with
  `sensor_id` suffixed by `_pressure` so the pressure sensor's temperature can be compared against the main one. A
  `pressure_temperature` of exactly `55.13` is treated as "no reading", since some devices send that instead of
  nulling the values.
* `vapor_density` (g/m³) is calculated from the temperature and humidity.
* Missing values are left out of the point. Non-numeric values get a `400` response and nothing is written.
* This was a Node.js function (`index.js`) until Oct 2026; it was ported to Python with the same behavior.

### Radio upload (`radio/`, retired)
Writes to the `atmospheric_noise` measurement.

```shell
curl http://[your_cloud_function_subdomain].cloudfunctions.net/upload_radio\
    \?fft_level\=-160.5\
    \&rms_level\=-170.3\
    \&site\=KPH\
    \&band\=630\
    \&receiver\=KiwiSDR15\
    \&maidenhead\=BL10rx\
    \&timestamp_ms\=1557379279758
```

Also accepts optional `c2_level` (field) and `grid` (tag).

### WSPR (`wspr/`, retired)
Writes to the `spot` measurement. A single spot can be sent with a GET:

```shell
curl "http://[your_cloud_function_subdomain].cloudfunctions.net/wspr\
?rcall=KI6NKO&rgrid=CM87&rqrg=14.0956\
&date=200119&time=2002&sig=-20&dt=0.3&drift=0\
&tqrg=14.097&tcall=K1ABC&tgrid=FN42&dbm=37&version=WD-1.0&mode=2"
```

`date` is `YYMMDD` and `time` is `HHMM`. Bulk upload via POST (`call`, `grid`, `qrg`, `version` and an `allmept`
file) is stubbed out but not implemented yet; the file isn't parsed.

### Ambient Weather (`ambient-weather/`)
Meant to be called on a schedule (e.g. Cloud Scheduler) with `?applicationKey=...&apiKey=...`. For each device on the
account it writes `environment_sensor` points for the outdoor sensors (`_outdoor`, including wind, rain, UV and solar
radiation), the indoor console (`_indoor`, including pressure) and any extra sensors 1–7 (`_1` … `_7`). Devices not in
`sensor_mapping` are named `<location> - <name>`. Note the Ambient Weather API is rate limited to 1 request/second per
API key.

### FireBoard (`fireboard/`)
Called every minute by the Cloud Scheduler job `tommy_fireboard`. Makes one `GET /api/v1/devices.json` call per run
(the API allows 17 calls per 5 minutes per user and only returns readings less than 60 seconds old) and writes
`environment_sensor` points:
* One point per temperature channel, `sensor_id` = `fireboard_<device title>_<probe label>` (slugified), with tags
  `name`, `label`, `model` and `original_sensor_id` = `<hardware_id>_<channel>`. Renaming a probe in the FireBoard app
  starts a new `sensor_id`; `original_sensor_id` stays the same for the physical channel.
* Temperatures are converted to °F. Humidity readings (`degreetype` 3, undocumented) are added to the device's
  channel 1 point (the Beacon's ambient sensor) with `vapor_density`, along with `battery_status` (0–1) and
  `signal_level` (dBm).
* Unplugged probes and powered-off FireBoards return nothing, so nothing is written.

Get an API token with `POST https://fireboard.io/api/rest-auth/login/` (`username`, `password`; a `User-Agent` header
is required) and put it in `.env` as `FIREBOARD_TOKEN`. For local runs, set `fireboard_token` and, to keep test data
separate, `sensor_id_prefix=test_fireboard`.

### Temperature LED (`temp-led/`)
Called with `?id=<n>` and returns a color (as a Python dict string, e.g. `{'red': 0, 'green': 255, 'blue': 0}`, or a
list of 7 of them for the 7-LED config). Configurations are hard coded in `main.py`:
* Temperature configs look up the latest `temperature` for an `original_sensor_id` and return `min_color`, `max_color`
  or `color` depending on whether it's below `min`, above `max`, or in range.
* Configured IDs are `1`, `3` (7-LED) and `4`. `id=2` was a PurpleAir air quality light; it was removed in Oct 2026
  after PurpleAir retired the endpoint it used. Unknown IDs return a `500`.

## Running locally
The Python functions can be run directly as a Flask debug server on `localhost:8000`:
```shell
cd ambient-weather
pip install -r requirements.txt flask requests
python3 main.py
curl 'http://localhost:8000/?applicationKey=...&apiKey=...'
```
`upload` has no `__main__` block; run it with `functions-framework`, which also matches the Cloud Functions
environment for the others:
```shell
cd upload
pip install -r requirements.txt functions-framework
influxdb_host=... influxdb_port=... influxdb_user=... influxdb_password=... influxdb_database=... \
    functions-framework --target=upload_function --port=8090
curl 'http://localhost:8090/?temperature=70&hum=50&heap=30000&sensor_id=test'
```
All functions read their configuration from `os.environ`, so set the environment variables inline when starting
them.
