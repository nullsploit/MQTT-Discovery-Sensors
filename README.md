# Custom-Sensors-MQTT

This is a custom sensor for Home Assistant that listens to a MQTT topic and parses the payload to extract sensor values.

## Requirements
| Name | Description |
| --- | --- |
| Docker | [Install Docker](https://docs.docker.com/engine/install/) |

## Docker build

```bash
docker build -t custom-sensors-mqtt:latest .
```

## Docker run

```bash
docker run -dit --restart unless-stopped --network host --name custom-sensors-mqtt -v [path-to-config]:/app/config -v [path-to-logs]:/app/logs custom-sensors-mqtt:latest
```

## Mount table
| Container path | Description |
| --- | --- |
| /app/config | Configuration files |
| /app/logs | Log files |

## Environment variable table
| Name | Description | Default |
| --- | --- | --- |
| TZ | Timezone | UTC |
| ONLINE_TIMEOUT | Time to wait before setting sensor to offline (minutes) | 1 |

## Example sensor-type configuration
See the below table for the sensor type options

```python
# sensor_config.py
sensor_types = [
    {
        "name": "Ultrasonic",
        "topic": "custom_sensors/v1/ultrasonic",
        "unit_of_measurement": "mm",
        "device_class": "distance",
    },{
        "name": "Sensor",
        "topic": "custom_sensors/v1/sensor",
        "unit_of_measurement": None,
        "device_class": None,
    },{
        "name": "Switch",
        "topic": "custom_sensors/v1/switch",
        "unit_of_measurement": None,
        "device_class": None,
        "command_topic": "custom_sensors/v1/switch/set",
    },
]
```

## Sensor type options
| Name | Description |
| --- | --- |
| name | Name of the sensor type |
| topic | MQTT topic to listen to |
| unit_of_measurement | Unit of measurement |
| device_class | Device class |
| command_topic | MQTT topic to send commands to (for switches) |
| min | Minimum value (for sliders) |
| max | Maximum value (for sliders) |
| options | List of options (for dropdowns) |

## Example mqtt configuration

```python
# mqtt_config.py
mqtt_config = {
    "host": "[HOST]",
    "port": [PORT],
    "username": "[USERNAME]",
    "password": "[PASSWORD]",
}
```

## Example of payload (to be parsed)
```
[device-id]|[sensor-name]|[value]
```

## Example of payload (send back if the sensor is a switch)
```
[device-id]|[sensor-name]|[value]
```
## !! Switch sensors must send a state update after receiving a command