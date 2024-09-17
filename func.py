import json
from time import sleep
import paho.mqtt.client as mqtt
from paho.mqtt.client import MQTTMessage
from logging.handlers import TimedRotatingFileHandler
import logging
from logging import Formatter
from datetime import datetime
import sys
import threading
import os

TYPE_SWITCH = 1
TYPE_SENSOR = 2

logger = logging.getLogger(__name__)

handler = TimedRotatingFileHandler(filename='./logs/worker.log', when='D', interval=1, backupCount=7, encoding='utf-8', delay=False)
formatter = Formatter(fmt='%(asctime)s %(name)s [%(levelname)s]: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class SensorType:
    def __init__(self, name=None, topic=None, unit_of_measurement=None, device_class=None, command_topic=None, options=None, min=None, max=None, step=None):
        self.name = name
        self.topic = topic
        self.unit_of_measurement = unit_of_measurement
        self.device_class = device_class
        self.command_topic = command_topic
        self.options = options
        self.min = min
        self.max = max
        self.step = step


class Sensor:
    def __init__(self, device_id=None, sensor_name=None, sensor_value=None, sensor_type=None, configured=False):
        self.device_id = device_id
        self.sensor_name = sensor_name
        self.sensor_value = sensor_value
        self.sensor_type: SensorType = sensor_type
        self.configured = configured
        self.sensor_flat_name = "_".join(sensor_name.lower().split(" "))
        self.device_flat_name = "_".join(device_id.lower().split(" "))
        self.last_updated = None

    def update(self, sensor_value):
        if not self.sensor_value == sensor_value:
            logger.info(f"Sensor [{self.sensor_type.name}] '{self.sensor_name}' updated: {self.sensor_value} -> {sensor_value}")
        self.sensor_value = sensor_value
        self.last_updated = datetime.now()



class SensorWorker:
    def __init__(self, mqttc=None, sensor_types=None, mqtt_config=None):
        self.mqttc: mqtt.Client = mqttc
        self.sensor_types = sensor_types
        self.configured = False
        self.online = False
        self.sensors = []
        self.mqtt_config = mqtt_config
        self.start()

    def sensor_last_update_worker(self):
        ONLINE_TIMEOUT = int(os.getenv("ONLINE_TIMEOUT", 1))
        timeout = ONLINE_TIMEOUT * 60
        while True:
            for sensor in self.sensors:
                sensor_obj: Sensor = sensor
                if sensor_obj.last_updated:
                    if (datetime.now() - sensor_obj.last_updated).total_seconds() > timeout:
                        self.sensor_offline(sensor_obj)
            sleep(10)

    def start(self):
        t = threading.Thread(target=self.sensor_last_update_worker)
        t.start()


    def connect(self):
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_message = self.on_message
        self.mqttc.on_disconnect = self.on_disconnect
        # self.mqttc.will_set("custom_sensors/v1/status", "offline", qos=1, retain=True)
        self.mqttc.username_pw_set(self.mqtt_config['username'], self.mqtt_config['password'])
        self.mqttc.connect(self.mqtt_config['host'], self.mqtt_config['port'], 60)
        self.mqttc.loop_forever()


    def reconnect(self):
        while not self.online:
            logger.info("Reconnecting...")
            self.mqttc.connect(self.mqtt_config['host'], self.mqtt_config['port'], 60)
            # sleep(5)
            self.mqttc.loop_forever()
            sleep(5)

    def on_disconnect(self, *args):
        # print("Disconnected")
        logger.error("Disconnected")
        self.online = False
        self.reconnect()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        logger.info(f"Connected with result code {reason_code}")
        self.online = True
        self.subscribe()
    
    def on_message(self, client, userdata, msg):
        msg_obj: MQTTMessage = msg
        topic = msg_obj.topic
        data = msg_obj.payload.decode()
        data_parts = data.split("|")
        # print(f"{topic}: {data}")

        if len(data_parts) >= 3:
            device_id = data_parts[0]
            sensor_name = data_parts[1]
            sensor_value = data_parts[2]
            sensor_type = None

            for sensor_type in self.sensor_types:
                sensor_type_obj: SensorType = sensor_type
                if sensor_type_obj.topic == topic:
                    sensor_type = sensor_type_obj
                    break
            
            found_sensor = False
            for sensor in self.sensors:
                sensor_obj: Sensor = sensor
                if sensor_obj.device_id == device_id and sensor_obj.sensor_name == sensor_name:
                    # sensor_obj.sensor_value = sensor_value
                    found_sensor: Sensor = sensor_obj
                    break

            if not found_sensor:
                sensor = Sensor(device_id=device_id, sensor_name=sensor_name, sensor_value=sensor_value, sensor_type=sensor_type)
                self.configure_sensor(sensor)
                # sleep(2)
                # self.update_sensor(sensor)
            else:
                found_sensor.update(sensor_value)
                self.update_sensor(found_sensor)
        else:
            for sensor in self.sensors:
                sensor_obj: Sensor = sensor
                if f"homeassistant/switch/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/set" == topic and sensor_obj.sensor_type.command_topic:
                    client.publish(f"{sensor_obj.sensor_type.command_topic}", f"{sensor_obj.device_id}|{sensor_obj.sensor_name}|{data}")
                if f"homeassistant/select/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/set" == topic and sensor_obj.sensor_type.command_topic:
                    client.publish(f"{sensor_obj.sensor_type.command_topic}", f"{sensor_obj.device_id}|{sensor_obj.sensor_name}|{data}")
                if f"homeassistant/number/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/set" == topic and sensor_obj.sensor_type.command_topic:
                    client.publish(f"{sensor_obj.sensor_type.command_topic}", f"{sensor_obj.device_id}|{sensor_obj.sensor_name}|{data}")



    def configure_sensor(self, sensor=None):
        sensor_obj: Sensor = sensor
        type_string = "sensor"
        message_data = {
            "device_class": sensor_obj.sensor_type.device_class,
            "name": sensor_obj.sensor_name,
            "state_topic": f"homeassistant/sensor/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/state",
            "unit_of_measurement": sensor_obj.sensor_type.unit_of_measurement,
            "value_template": """{{ value_json.$name }}""".replace("$name", sensor_obj.sensor_flat_name),
            "unique_id": f"{sensor_obj.device_flat_name}_{sensor_obj.sensor_flat_name}",
            "platform": "mqtt",
            "availability_topic": f"homeassistant/{sensor_obj.device_flat_name}_{sensor_obj.sensor_flat_name}/availability",
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": {
                "identifiers": [sensor_obj.device_flat_name],
                "name": sensor_obj.device_id,
                "model": sensor_obj.sensor_type.name,
                "manufacturer": "Fontana Software",
            }
        }
        if sensor_obj.sensor_type.command_topic and not sensor_obj.sensor_type.options and not sensor_obj.sensor_type.min and not sensor_obj.sensor_type.max:
            type_string = "switch"
            message_data["state_topic"] = f"homeassistant/{type_string}/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/state"
            message_data["command_topic"] = f"homeassistant/{type_string}/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/set"
            message_data["state_on"] = "on"
            message_data["state_off"] = "off"
            message_data["payload_on"] = "on"
            message_data["payload_off"] = "off"
        if sensor_obj.sensor_type.options and not sensor_obj.sensor_type.min:
            type_string = "select"
            message_data["options"] = sensor_obj.sensor_type.options
            message_data["state_topic"] = f"homeassistant/{type_string}/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/state"
            message_data["command_topic"] = f"homeassistant/{type_string}/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/set"
        if sensor_obj.sensor_type.min and sensor_obj.sensor_type.max and sensor_obj.sensor_type.step:
            type_string = "number"
            message_data["state_topic"] = f"homeassistant/{type_string}/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/state"
            message_data["command_topic"] = f"homeassistant/{type_string}/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/set"
            message_data["min"] = sensor_obj.sensor_type.min
            message_data["max"] = sensor_obj.sensor_type.max
            message_data["step"] = sensor_obj.sensor_type.step
        self.mqttc.publish(f"homeassistant/{type_string}/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/config", json.dumps(message_data))
        sensor_obj.configured = True
        self.sensors.append(sensor_obj)
        logger.info(f"Sensor [{sensor_obj.sensor_type.name}] type:{type_string} '{sensor_obj.sensor_name}' configured")
        sensor_obj.update(sensor_obj.sensor_value)
        self.update_sensor(sensor_obj)


    def sensor_offline(self, sensor=None):
        sensor_obj: Sensor = sensor
        self.mqttc.publish(f"homeassistant/{sensor_obj.device_flat_name}_{sensor_obj.sensor_flat_name}/availability", "offline")
        # remove sensor from list
        self.sensors.remove(sensor_obj)
        logger.info(f"Sensor [{sensor_obj.sensor_type.name}] '{sensor_obj.sensor_name}' offline")



    def update_sensor(self, sensor=None):
        sensor_obj: Sensor = sensor
        sensor_obj.last_updated = datetime.now()
        message_data = {
            f"{sensor_obj.sensor_flat_name}": sensor_obj.sensor_value
        }
        type_string = "sensor"
        if sensor_obj.sensor_type.command_topic and not sensor_obj.sensor_type.options and not sensor_obj.sensor_type.min and not sensor_obj.sensor_type.max:
            type_string = "switch"
        if sensor_obj.sensor_type.options:
            type_string = "select"
        if sensor_obj.sensor_type.min and sensor_obj.sensor_type.max and sensor_obj.sensor_type.step:
            type_string = "number"
        self.mqttc.publish(f"homeassistant/{sensor_obj.device_flat_name}_{sensor_obj.sensor_flat_name}/availability", "online")
        self.mqttc.publish(f"homeassistant/{type_string}/{sensor_obj.device_flat_name}/{sensor_obj.sensor_flat_name}/state", json.dumps(message_data))

    def subscribe(self):
        for sensor_type_pre in self.sensor_types:
            sensor_type: SensorType = sensor_type_pre
            self.mqttc.subscribe(sensor_type.topic)
            if sensor_type.command_topic and not sensor_type.options:
                self.mqttc.subscribe(f"homeassistant/switch/#")
            if sensor_type.options:
                self.mqttc.subscribe(f"homeassistant/select/#")
            if sensor_type.min and sensor_type.max:
                self.mqttc.subscribe(f"homeassistant/number/#")
        logger.info("Subscribed to topics")

    