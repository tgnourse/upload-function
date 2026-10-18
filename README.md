# upload-function
A collection of Google Cloud Functions for getting environmental and radio data into an InfluxDB instance (and, in
one case, back out again).

| Directory | Language | Entry point | What it does |
|---|---|---|---|
| `/` (root) | Node.js | `uploadFunction` | Receives temperature/humidity/pressure readings from sensors via HTTP. |
| `radio/` | Node.js | `uploadFunction` | Receives atmospheric noise levels from radio receivers via HTTP. |
| `wspr/` | Python | `upload_function` | Receives [WSPR](https://en.wikipedia.org/wiki/WSPR_(amateur_radio_software)) spots in the same format as [WSPRnet](http://wsprnet.org/). |
| `ambient-weather/` | Python | `upload_function` | Pulls the latest readings from the [Ambient Weather API](https://www.ambientweather.com/api.html) for personal weather stations. |
| `signals-thermometer/` | Python | `upload_function` | Pulls probe temperatures for a ThermoWorks Signals thermometer from its Firebase backend. |
| `temp-led/` | Python | `get_function` | Reads the latest value for a sensor (or PurpleAir PM2.5) and returns an RGB color for an LED indicator. |

## Configuration
Every function reads the InfluxDB connection details from environment variables:
* `influxdb_user`: The user. For the upload functions it only needs `WRITE` access to the DB; `temp-led` needs `READ`.
* `influxdb_password`: The user's password.
* `influxdb_host`: Host IP or domain. All functions connect over `https` and **do not verify the certificate**, since
  the InfluxDB instance uses a self-signed cert.
* `influxdb_port`: The port.
* `influxdb_database`: The database name.

Some functions take additional environment variables:
* `sensor_mapping` (root, `ambient-weather`): A JSON object mapping a raw sensor ID to a friendlier name, which is
  written as the `sensor_id` tag (the raw ID is kept in `original_sensor_id`). See `sensor_mapping.json` and
  `ambient-weather/sensor_mapping.json` for the current mappings; these files are just a record of what is configured
  in production, the functions don't read them directly.
* `api_key` (`signals-thermometer`): The Firebase web API key used to log in.

## Deploying
Each directory is deployed as its own function. Something along these lines:
```shell
gcloud functions deploy upload --source=. --entry-point=uploadFunction \
    --runtime=nodejs20 --trigger-http --env-vars-file=env.yaml
```
For the Python functions, use the directory as `--source`, a Python runtime, and the entry point from the table above.

## Functions

### Environmental upload (root)
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

### Radio upload (`radio/`)
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

### WSPR (`wspr/`)
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

### Signals thermometer (`signals-thermometer/`)
Meant to be called on a schedule with `?email=...&password=...&device_id=...&device_name=...`. Logs in to Firebase,
fetches the probe names and the last 50 readings, and writes one `environment_sensor` point per probe reading, named
`<device_name>-<probe name>`. Probes reading `---` are skipped.

### Temperature LED (`temp-led/`)
Called with `?id=<n>` and returns a color (as a Python dict string, e.g. `{'red': 0, 'green': 255, 'blue': 0}`, or a
list of 7 of them for the 7-LED config). Configurations are hard coded in `main.py`:
* Temperature configs look up the latest `temperature` for an `original_sensor_id` and return `min_color`, `max_color`
  or `color` depending on whether it's below `min`, above `max`, or in range.
* The air quality config fetches PM2.5 from PurpleAir and returns a color matching the EPA AQI band.

## Running locally
The Python functions can be run directly as a Flask debug server on `localhost:8000`:
```shell
cd ambient-weather
pip install -r requirements.txt flask requests
python3 main.py
curl 'http://localhost:8000/?applicationKey=...&apiKey=...'
```
`ambient-weather` reads its configuration from `os.environ`, so set the environment variables inline when starting it.
The other Python functions still read `request.environ` (which only works on the retired `python37` runtime), so for
local runs the values need to be injected into the request in the `__main__` block (`temp-led` has placeholders
showing how). Alternatively, run any of them with
`functions-framework --target=<entry point>` to match the Cloud Functions environment.
