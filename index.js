const Influx = require('influx');

/**
 * Responds to any HTTP request.
 *
 * @param {!express:Request} req HTTP request context. See http://expressjs.com/en/api.html#req
 * @param {!express:Response} res HTTP response context.
 */
exports.uploadFunction = (req, res) => {
    const influxdb_user = process.env.influxdb_user;
    const influxdb_password = process.env.influxdb_password;
    const influxdb_host = process.env.influxdb_host;
    const influxdb_port = process.env.influxdb_port;
    const influxdb_database = process.env.influxdb_database;

    // Maps between sensor_id and a better name for that sensor. Note that it doesn't do anything
    // special to check for overlap, etc.
    let sensor_mapping = {};
    try {
        sensor_mapping_str = process.env.sensor_mapping;
        // Use the below for testing.
        // sensor_mapping_str = '{"test" : "test_alias"}';
        sensor_mapping = JSON.parse(sensor_mapping_str);
        console.log(`Using this sensor mapping: ${JSON.stringify(sensor_mapping)}`);
    } catch (e) {
        console.error(
            `Problem parsing sensor_mapping env variable: "${sensor_mapping_str}" with error ${e}`);
    }

    const influxdb_protocol = 'https';

    console.log('Setting up InfluxDB connection with' +
        ' user:' + influxdb_user +
        ' host:' + influxdb_host +
        ' port:' + influxdb_port +
        ' database:' + influxdb_database);

    // Tell node to ignore TLS rejections because the InfluxDB certificate is self signed.
    process.env['NODE_TLS_REJECT_UNAUTHORIZED'] = 0;

    const measurement = 'environment_sensor';

    const influx = new Influx.InfluxDB({
        host: influxdb_host,
        port: influxdb_port,
        protocol: influxdb_protocol,
        username: influxdb_user,
        password: influxdb_password,
        database: influxdb_database,
        schema: [
            {
                measurement: measurement,
                fields: {
                    temperature: Influx.FieldType.FLOAT, // F
                    humidity: Influx.FieldType.FLOAT, // %
                    vapor_density: Influx.FieldType.FLOAT, // g/m^3
                    pressure_temperature: Influx.FieldType.FLOAT, // F
                    pressure: Influx.FieldType.FLOAT, // inHg
                    heap: Influx.FieldType.INTEGER, // B
                },
                tags: [
                    'sensor_id', 'original_sensor_id', 'ip', 'ssid'
                ]
            }
        ]
    });

    // Some hard coded data for testing without query parameters.
    // const temperature = 81.316319523919;
    // const humidity = 43.363088426032;
    // const heap = 33752;
    // const ip = '192.168.1.132';
    // const ssid = 'Blinky';
    // const sensor_id = 'tgnourse12';

    // Collect the data from the HTTP request query parameters.
    console.log('Query Parameters:');
    console.log(req.query);
    const temperature = req.query['temperature'];
    const humidity = req.query['hum'];
    const heap = req.query['heap'];
    const ip = req.query['ip'];
    const ssid = req.query['ssid'];
    const sensor_id = req.query['sensor_id'];
    let pressure = req.query['pressure'];
    let pressure_temperature = req.query['pressure_temperature'];

    // Some devices don't nil out the pressure data correctly. Correct it here.
    if (pressure_temperature == "55.13") {
        pressure = null;
        pressure_temperature = null;
    }

    // Below this is calculated.
    const temp_c = (temperature - 32) * (5.0/9.0);
    const saturation_vapor_density = 5.018+0.32321*temp_c+8.1847*0.0081847*temp_c*temp_c+0.00031243*temp_c*temp_c*temp_c;
    const vapor_density = (humidity / 100.0) * saturation_vapor_density;

    // Alias the sensor_id if necessary.
    let sensor_id_alias = sensor_id;
    if (sensor_id in sensor_mapping) {
        sensor_id_alias = sensor_mapping[sensor_id];
    }

    const point = {
        measurement: measurement,
        fields: {
            temperature: temperature,
            humidity: humidity,
            vapor_density: vapor_density,
            pressure: pressure,
            pressure_temperature: pressure_temperature,
            heap: heap
        }, tags: { sensor_id: sensor_id_alias, original_sensor_id: sensor_id, ip: ip, ssid: ssid }
    };

    let points = [point];

    // If there's a pressure value, add a separate point for that. This is so the temperatures can be directly compared.
    let pressure_point = null;
    if (pressure) {
        pressure_point = {
            measurement: measurement,
            fields: {
                temperature: pressure_temperature,
                pressure: pressure,
                pressure_temperature: pressure_temperature,
                heap: heap
            }, tags: {sensor_id: sensor_id_alias + "_pressure", original_sensor_id: sensor_id, ip: ip, ssid: ssid}
        };
        points.push(pressure_point);
    }

    console.log('Going to write these points to InfluxDB:');
    console.log(points);

    // Go ahead and write the data.
    influx.writePoints(points)
        .catch(err => {
            console.error(`Error saving data to InfluxDB! ${err.stack}`);
            res.status(500).send(`Error saving data to InfluxDB! ${err.stack}`)
        }).then(() => {
            // TODO: Figure out how to send this only on success, it works as is but it's confusing.
            console.log('Successfully wrote!');
            res.status(200).send(`Successfully wrote to ` +
                `${influxdb_protocol}://${influxdb_host}:${influxdb_port}/${influxdb_database} ` +
                `as ${influxdb_user} with this data:` +
                `\n${JSON.stringify(point)}`);
        });

    // Code for querying. Use for debugging if needed but note that the user might not have READ
    // access.
    // console.log('Attempting to query latest data.');
    // influx.query(`select * from ${measurement} limit 1`)
    //     .then(result => {
    //         console.log('Results were fetched ... returning.');
    //         res.status(200).json(result)
    //     }).catch(err => {
    //     res.status(500).send(`Error querying data from InfluxDB! ${err.stack}`)
    // });
    // console.log('Query was attempted ... ');
};