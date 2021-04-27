# Support for Inkbird IBS-TH1 Bluetooth Thermometer & Hygrometer Logger including external probe
# From: https://github.com/zewelor/bt-mqtt-gateway/issues/179
#
# Example configuration in config.yaml:
#    ibsth1:
#      args:
#        devices:
#          ibsth1: xx:xx:xx:xx:xx:xx
#        topic_prefix: inkbird
#      update_interval: 60
##
import time
from mqtt import MqttMessage
from workers.base import BaseWorker
import logger

REQUIREMENTS = ["bluepy"]
_LOGGER = logger.get(__name__)

class Ibsth1Worker(BaseWorker):
    def searchmac(self, devices, mac):
        for dev in devices:
            if dev.addr == mac.lower():
                return dev
        return None

    def status_update(self):
        from bluepy.btle import Scanner, DefaultDelegate

        class ScanDelegate(DefaultDelegate):
            def __init__(self):
                DefaultDelegate.__init__(self)

            def handleDiscovery(self, dev, isNewDev, isNewData):
                if isNewDev:
                    _LOGGER.debug("Discovered new device: %s" % dev.addr)

        scanner = Scanner().withDelegate(ScanDelegate())
        devices = scanner.scan(5.0)
        ret = []

        for name, mac in self.devices.items():
            device = self.searchmac(devices, mac)
            if device is None:
                ret.append(
                    MqttMessage(
                        topic=self.format_topic(name + "/presence"), payload="0"
                    )
                )
            else:
                ret.append(
                    MqttMessage(
                        topic=self.format_topic(name + "/presence/rssi"),
                        payload=device.rssi,
                    )
                )
                ret.append(
                    MqttMessage(
                        topic=self.format_topic(name + "/presence"), payload="1"
                    )
                )
                readBuffer=device.getValueText(255)
                _LOGGER.debug("text: %s" % readBuffer)
                if readBuffer is not None:
                  bytes_ = bytearray(bytes.fromhex(readBuffer))
                  temperature_raw_value = bytes_[1] * 256 + bytes_[0]
                  if temperature_raw_value >= 0x8000:
                     temperature_ibsth1=(temperature_raw_value - 0x10000) / 100
                  else:
                     temperature_ibsth1=temperature_raw_value / 100
                  ret.append(
                      MqttMessage(
                          topic=self.format_topic(name + "/externalSensor"), payload=bytes_[4]
                      )
                  )
                  ret.append(
                      MqttMessage(
                          topic=self.format_topic(name + "/battery"), payload=bytes_[7]
                      )
                  )
                  ret.append(
                      MqttMessage(
                          topic=self.format_topic(name + "/temperature"),
                          payload=temperature_ibsth1,
                      )
                  )
                  ret.append(
                      MqttMessage(
                          topic=self.format_topic(name + "/humidity"),
                          payload=(bytes_[3] * 256 + bytes_[2])/100,
                      )
                  )
            yield ret
