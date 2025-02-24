import json
import logger

from contextlib import contextmanager

from mqtt import MqttMessage
from workers.base import BaseWorker

_LOGGER = logger.get(__name__)

REQUIREMENTS = ["bluepy"]

class Lywsd03MmcWorker(BaseWorker):
    def _setup(self):
        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))

        for name, mac in self.devices.items():
            _LOGGER.info("Adding %s device '%s' (%s)", repr(self), name, mac)
            self.devices[name] = lywsd03mmc(mac, command_timeout=self.command_timeout, passive=self.passive)

    def find_device(self, mac):
        for name, device in self.devices.items():
            if device.mac == mac:
                return device
        return

    def status_update(self):
        from bluepy import btle

        if self.passive:
            scanner = btle.Scanner()
            results = scanner.scan(self.scan_timeout if hasattr(self, 'scan_timeout') else 20.0, passive=True)

            for res in results:
                device = self.find_device(res.addr)
                if device:
                    for (adtype, desc, value) in res.getScanData():
                        if ("1a18" in value):
                            _LOGGER.debug("%s - received scan data %s", res.addr, value)
                            device.processScanValue(value)

        for name, lywsd03mmc in self.devices.items():
            try:
                ret = lywsd03mmc.readAll()
            except btle.BTLEDisconnectError as e:
                self.log_connect_exception(_LOGGER, name, e)
            except btle.BTLEException as e:
                self.log_unspecified_exception(_LOGGER, name, e)
            else:
                yield [MqttMessage(topic=self.format_topic(name), payload=json.dumps(ret))]


class lywsd03mmc:
    def __init__(self, mac, command_timeout=30, passive=False):
        self.mac = mac
        self.passive = passive
        self.command_timeout = command_timeout

        self._temperature = None
        self._humidity = None
        self._battery_level = None
        self._battery_voltage = None

    @contextmanager
    def connected(self):
        from bluepy import btle

        _LOGGER.debug("%s - connected ", self.mac)
        device = btle.Peripheral()
        device.connect(self.mac)
        device.writeCharacteristic(0x0038, b'\x01\x00', True)
        device.writeCharacteristic(0x0046, b'\xf4\x01\x00', True)
        yield device

    def readAll(self):
        if self.passive:
            temperature = self.getTemperature()
            humidity = self.getHumidity()
            battery_level = self.getBattery_level()
            battery_voltage = self.getBattery_voltage()
        else:
            with self.connected() as device:
                self.getData(device)
                temperature = self.getTemperature()
                humidity = self.getHumidity()
                battery_level = self.getBattery_level()
                battery_voltage = self.getBattery_voltage()

        if temperature and humidity and battery_level and battery_voltage:
            _LOGGER.debug("%s - found values %s, %s, %s, %s", self.mac, temperature, humidity, battery_level, battery_voltage)
        else:
            _LOGGER.debug("%s - no data received", self.mac)

        return {
            "temperature": temperature,
            "humidity": humidity,
            "battery_level": battery_level,
            "battery_voltage": battery_voltage,
        }

    def getData(self, device):
        self.subscribe(device)
        while True:
            if device.waitForNotifications(self.command_timeout):
                break
        return self._temperature, self._humidity, self._battery_level, self._battery_voltage

    def getTemperature(self):
        return self._temperature;

    def getHumidity(self):
        return self._humidity;

    def getBattery_level(self):
        return self._battery_level;

    def getBattery_voltage(self):
        return self._battery_voltage;

    def subscribe(self, device):
        device.setDelegate(self)

    def processScanValue(self, data):
        _LOGGER.debug("!!!!ProcessScanValue: calc temp, humidity, and bat!!!!!")
        _LOGGER.debug(f"!!!!Data is {data}!!!!")
        temperature = int(data[16:20], 16) / 10
        humidity = int(data[20:22], 16)
        battery_level = int(data[22:24], 16)
        battery_voltage = int(data[24:28], 16) / 1000
        _LOGGER.debug(f"!!!!!Calculated: T={temperature}, H={humidity}, BL={battery_level}, BV={battery_voltage}")

        self._temperature = round(temperature, 1)
        self._humidity = round(humidity,1)
        self._battery_level = round(battery_level, 1)
        self._battery_voltage = round(battery_voltage, 4)

    def handleNotification(self, handle, data):
        _LOGGER.debug("!!!!!handleNotification: temp, humiditiy, and bat!!!!!")
        temperature = int.from_bytes(data[0:2], byteorder='little', signed=True) / 100
        humidity = int.from_bytes(data[2:3], byteorder='little')
        battery_level = int.from_bytes(data[3:5], byteorder='little') / 1000

        self._temperature = round(temperature, 1)
        self._humidity = round(humidity)
        self._battery_level = round(battery, 4)
