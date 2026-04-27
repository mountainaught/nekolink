# py_e4lib/client.py

import logging
import struct
import time
from typing import Optional, Callable
from bleak import BleakClient, BleakScanner

from .constants import BVP_UUID, GSR_UUID, ACC_UUID, TEMP_UUID, CMD_UUID, DEVICE_NAME_FILTER
from .parsers import parse_bvp, parse_gsr, parse_temp, parse_acc

log = logging.getLogger(__name__)

# Maps sensor name -> (uuid, parser)
_SENSORS = {
    "bvp":  (BVP_UUID,  parse_bvp),
    "gsr":  (GSR_UUID,  parse_gsr),
    "temp": (TEMP_UUID, parse_temp),
    "acc":  (ACC_UUID,  parse_acc),
}


class E4Client:
    def __init__(self, address: str):
        self.address = address
        self._client: Optional[BleakClient] = None
        self._connected = False
        self._callbacks: dict[str, Callable] = {}

    @classmethod
    async def find(cls, timeout: float = 10.0):
        log.info("Scanning for '%s' devices...", DEVICE_NAME_FILTER)
        device = await BleakScanner.find_device_by_filter(
            lambda d, _ad: d.name and DEVICE_NAME_FILTER in d.name,
            timeout=timeout,
        )
        if not device:
            log.warning("No device found within %ss", timeout)
            return None
        log.info("Found %s (%s)", device.name, device.address)
        return cls(device.address)

    def on(self, sensor: str, callback: Callable):
        if sensor not in _SENSORS:
            raise ValueError(f"Unknown sensor '{sensor}', expected one of {list(_SENSORS)}")
        self._callbacks[sensor] = callback

    async def connect(self):
        if self._connected:
            return
        self._client = BleakClient(self.address)
        await self._client.connect()
        self._connected = True
        log.info("Connected to %s", self.address)

    async def disconnect(self):
        if not self._connected or not self._client:
            return
        for name in self._callbacks:
            uuid, _ = _SENSORS[name]
            await self._client.stop_notify(uuid)
        await self._client.disconnect()
        self._connected = False
        log.info("Disconnected")

    async def start(self):
        if not self._connected:
            raise RuntimeError("Not connected — call connect() first")

        for name, cb in self._callbacks.items():
            uuid, parser = _SENSORS[name]

            def _make_handler(parse, callback):
                def handler(_sender, data: bytes):
                    values = parse(data)
                    if values:
                        callback(values)
                return handler

            await self._client.start_notify(uuid, _make_handler(parser, cb))

        await self._client.write_gatt_char(
            CMD_UUID, struct.pack("<BI", 1, int(time.time()))
        )
        log.info("Streaming started")

    async def stop(self):
        await self.disconnect()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.stop()