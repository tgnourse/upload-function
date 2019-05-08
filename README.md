# upload-function
Google Cloud Function for uploading environmental data to an InfluxDB instance.

Takes the following environmental variables:
* `influxdb_user`: The user.
* `influxdb_password`: Duh.
* `influxdb_host`: Host IP or domain. Note that the code assumes `https`.
* `influxdb_port`: Duh.
* `influxdb_database`: Note the user only needs `WRITE` access to the DB.

Send data like this:
```shell
curl http://[your_cloud_function_subdomain].cloudfunctions.net/upload\
    \?temperature\=81.340352483406\
    \&hum\=44.689097428855\
    \&heap\=33752\
    \&ip\=192.168.1.132\
    \&ssid\=SSID\
    \&sensor_id\=Sensor1
```
