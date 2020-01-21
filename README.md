# upload-function
Google Cloud Function for uploading environmental or radio data to an InfluxDB instance.

Takes the following environmental variables:
* `influxdb_user`: The user.
* `influxdb_password`: Duh.
* `influxdb_host`: Host IP or domain. Note that the code assumes `https`.
* `influxdb_port`: Duh.
* `influxdb_database`: Note the user only needs `WRITE` access to the DB.

Send data for environmental upload like this:
```shell
curl http://[your_cloud_function_subdomain].cloudfunctions.net/upload\
    \?temperature\=81.340352483406\
    \&hum\=44.689097428855\
    \&heap\=33752\
    \&ip\=192.168.1.132\
    \&ssid\=SSID\
    \&sensor_id\=Sensor1
```

Send data for radio upload like this:

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

Includes additional functions for the following:
* `/wspr` - upload [WSPR](https://en.wikipedia.org/wiki/WSPR_(amateur_radio_software)) spots in the same format as for
[WSPRnet](http://wsprnet.org/)
* `ambient-weather` - pulls data from the [Ambient Weather API](https://www.ambientweather.com/api.html) for personal
weather stations.
