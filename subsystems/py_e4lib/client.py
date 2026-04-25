# py_e4lib/client.py

import asyncio
import struct
import time
from typing import Optional, Callable, List, Tuple
from bleak import BleakClient, BleakScanner

from .constants import (
    BVP_UUID, GSR_UUID, ACC_UUID, TEMP_UUID, CMD_UUID,
    DEVICE_NAME_FILTER
)
from .parsers import parse_bvp, parse_gsr, parse_temp, parse_acc


class E4Client:
    """
    Async BLE client for Empatica E4 devices.

    Usage:
        async with E4Client.find() as client:
            client.enable_bvp(lambda values: print(f"BVP: {values}"))
            await client.start()
            await asyncio.sleep(60)
    """

    def __init__(self, address: str):
        """
        Create client for specific BLE address.
        Use E4Client.find() to auto-discover device.
        """
        self.address = address
        self._client: Optional[BleakClient] = None
        self._connected = False

        # User callbacks
        self._bvp_callback: Optional[Callable[[List[Tuple[int, int]]], None]] = None
        self._gsr_callback: Optional[Callable[[List[float]], None]] = None
        self._temp_callback: Optional[Callable[[List[float]], None]] = None
        self._acc_callback: Optional[Callable[[List[Tuple[int, int, int]]], None]] = None

    @classmethod
    async def find(cls, timeout: float = 10.0) -> "E4Client":
        """
        Scan for first device with 'Empatica' in name.

        Args:
            timeout: Scan timeout in seconds

        Returns:
            E4Client instance

        Raises:
            RuntimeError: If no device found
        """
        print(f"Scanning for devices with '{DEVICE_NAME_FILTER}' in name...")
        device = await BleakScanner.find_device_by_filter(
            lambda d, ad: d.name and DEVICE_NAME_FILTER in d.name,
            timeout=timeout
        )

        if not device:
            raise RuntimeError(f"No device found with '{DEVICE_NAME_FILTER}' in name")

        print(f"Found device: {device.name} ({device.address})")
        return cls(device.address)

    async def connect(self):
        """Connect to the E4 device."""
        if self._connected:
            return

        print(f"Connecting to {self.address}...")
        self._client = BleakClient(self.address)
        await self._client.connect()
        self._connected = True
        print("Connected!")

    async def disconnect(self):
        """Disconnect from the E4 device."""
        if not self._connected or not self._client:
            return

        # Stop notifications
        if self._bvp_callback:
            await self._client.stop_notify(BVP_UUID)
        if self._gsr_callback:
            await self._client.stop_notify(GSR_UUID)
        if self._temp_callback:
            await self._client.stop_notify(TEMP_UUID)
        if self._acc_callback:
            await self._client.stop_notify(ACC_UUID)

        await self._client.disconnect()
        self._connected = False
        print("Disconnected")

    def enable_bvp(self, callback: Callable[[List[Tuple[int, int]]], None]):
        """
        Enable BVP (Blood Volume Pulse) stream.

        Args:
            callback: Function called with list of BVP values (floats)
        """
        self._bvp_callback = callback

    def enable_gsr(self, callback: Callable[[List[float]], None]):
        """
        Enable GSR/EDA (Galvanic Skin Response) stream.

        Args:
            callback: Function called with list of EDA values in microsiemens (floats)
        """
        self._gsr_callback = callback

    def enable_temp(self, callback: Callable[[List[float]], None]):
        """
        Enable temperature stream.

        Args:
            callback: Function called with list of temperature values in Celsius (floats)
        """
        self._temp_callback = callback

    def enable_acc(self, callback: Callable[[List[Tuple[int, int, int]]], None]):
        """
        Enable accelerometer stream.

        Args:
            callback: Function called with list of (x, y, z) tuples.
                     Divide by 64.0 to get g-force.
        """
        self._acc_callback = callback

    async def start(self):
        """Start streaming data from enabled sensors."""
        if not self._connected or not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        # Set up notifications for enabled sensors
        if self._bvp_callback:
            await self._client.start_notify(BVP_UUID, self._handle_bvp)
        if self._gsr_callback:
            await self._client.start_notify(GSR_UUID, self._handle_gsr)
        if self._temp_callback:
            await self._client.start_notify(TEMP_UUID, self._handle_temp)
        if self._acc_callback:
            await self._client.start_notify(ACC_UUID, self._handle_acc)

        # Send start command
        command = struct.pack('<BI', 1, int(time.time()))
        await self._client.write_gatt_char(CMD_UUID, command)
        print("Streaming started")

    async def stop(self):
        """Stop streaming and disconnect."""
        await self.disconnect()

    # Internal notification handlers
    def _handle_bvp(self, sender, data: bytes):
        """Internal handler for BVP notifications."""
        values = parse_bvp(data)
        if values and self._bvp_callback:
            self._bvp_callback(values)

    def _handle_gsr(self, sender, data: bytes):
        """Internal handler for GSR notifications."""
        values = parse_gsr(data)
        if values and self._gsr_callback:
            self._gsr_callback(values)

    def _handle_temp(self, sender, data: bytes):
        """Internal handler for temperature notifications."""
        values = parse_temp(data)
        if values and self._temp_callback:
            self._temp_callback(values)

    def _handle_acc(self, sender, data: bytes):
        """Internal handler for accelerometer notifications."""
        values = parse_acc(data)
        if values and self._acc_callback:
            self._acc_callback(values)

    # Context manager support
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
