import paho.mqtt.client as mqtt
from config.sensor_config import *
from config.mqtt_config import mqtt_config
from func import *


sensor_type_objs = []
for sensor_type in sensor_types:
    sensor_type_obj = SensorType(
        name=sensor_type['name'], 
        topic=sensor_type["topic"], 
        unit_of_measurement=sensor_type["unit_of_measurement"], 
        device_class=sensor_type["device_class"],
        command_topic=sensor_type.get("command_topic", None),
        options=sensor_type.get("options", None),
        min=sensor_type.get("min", None),
        max=sensor_type.get("max", None),
        step=sensor_type.get("step", 1),
    )
    sensor_type_objs.append(sensor_type_obj)



mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
worker = SensorWorker(mqttc, sensor_type_objs, mqtt_config)
worker.connect()

# mqttc.on_connect = worker.on_connect
# mqttc.on_message = worker.on_message
# mqttc.on_disconnect = worker.on_disconnect
# mqttc.will_set("custom_sensors/v1/status", "offline", qos=1, retain=True)
# mqttc.username_pw_set(mqtt_config['username'], mqtt_config['password'])
# mqttc.connect(mqtt_config['host'], mqtt_config['port'], 60)
# mqttc.loop_forever()
