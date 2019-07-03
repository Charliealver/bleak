"""
BLE Client for CoreBluetooth on macOS

Created on 2019-6-26 by kevincar <kevincarrolldavis@gmail.com>
"""

import logging
import asyncio

from typing import Callable, Any

from Foundation import NSData, CBUUID

from asyncio.events import AbstractEventLoop
from bleak.exc import BleakError

from bleak.backends.device import BLEDevice
from bleak.backends.corebluetooth import Application
from bleak.backends.client import BaseBleakClient
from bleak.backends.service import BleakGATTServiceCollection

from bleak.backends.corebluetooth.service import BleakGATTServiceCoreBluetooth
from bleak.backends.corebluetooth.characteristic import BleakGATTCharacteristicCoreBluetooth
from bleak.backends.corebluetooth.descriptor import BleakGATTDescriptorCoreBluetooth

logger = logging.getLogger(__name__)

class BleakClientCoreBluetooth(BaseBleakClient):
    """
    CoreBluetooth class interface for BleakClient
    """

    def __init__(self, address: str, loop: AbstractEventLoop, **kwargs):
        super(BleakClientCoreBluetooth, self).__init__(address, loop, **kwargs)

        self.app = Application(client=True)
        self._device_info = None
        self._requester = None
        self._callbacks = {}
        self._services = None

    def __str__(self):
        return "BleakClientCoreBluetooth ({})".format(self.address)

    async def is_ready(self):
        await self.app._is_delegate_ready()

    async def connect(self) -> bool:
        """
        Connect to a specified Peripheral
        """

        devices = await self.scan_for_devices(10.0)
        sought_device = list(filter(lambda x: x.address.upper() == self.address.upper(), devices))

        if len(sought_device):
            self._device_info = sought_device[0].details
        else:
            raise BleakError("Device with address {} was not found".format(self.address))

        logger.debug("Connecting to BLE device @ {}".format(self.address))

        await self.app.central_manager_delegate.connect_(sought_device[0].details)
        
        # Now get services
        await self.get_services()

        return True

    async def disconnect(self) -> bool:
        """Disconnect from the peripheral device"""
        await self.app.central_manager_delegate.disconnect()
        return True

    async def is_connected(self) -> bool:
        """Checks for current active connection"""
        return self.app.central_manager_delegate.isConnected

    async def scan_for_devices(self, timeout: float = 10.0) -> [BLEDevice]:
        """Scan for peripheral devices"""
        peripherals = await self.app.central_manager_delegate.scanForPeripherals_({'timeout': timeout}) 

        found = []
        for i, peripheral in enumerate(peripherals):
            address = peripheral.identifier().UUIDString()
            name = peripheral.name() or "Unknown"
            details = peripheral
    
            advertisement_data = self.app.central_manager_delegate.advertisement_data_list[i]
            manufacturer_binary_data = advertisement_data['kCBAdvDataManufacturerData'] if 'kCBAdvDataManufacturerData' in advertisement_data.keys() else None
            manufacturer_data = {}
            if manufacturer_binary_data:
                manufacturer_id = int.from_bytes(manufacturer_binary_data[0:2], byteorder='little')
                manufacturer_value = ''.join(list(map(lambda x: format(x, 'x') if len(format(x, 'x')) == 2 else "0{}".format(format(x, 'x')), list(manufacturer_binary_data)[2:])))
                manufacturer_data = {
                        manufacturer_id: manufacturer_value
                        }
    
                found.append(BLEDevice(address, name, details, manufacturer_data=manufacturer_data))
    
        return found

    async def get_services(self) -> BleakGATTServiceCollection:
        """Get all services registered for this GATT server.

        Returns:
           A :py:class:`bleak.backends.service.BleakGATTServiceCollection` with this device's services tree.

        """
        if self._services != None:
            return self._services

        logger.debug("retreiving services...")
        services = await self.app.central_manager_delegate.connected_peripheral_delegate.discoverServices()

        for service in services:
            serviceUUID = service.UUID().UUIDString()
            logger.debug("retreiving characteristics for service {}".format(serviceUUID))
            characteristics = await self.app.central_manager_delegate.connected_peripheral_delegate.discoverCharacteristics_(service)

            self.services.add_service(BleakGATTServiceCoreBluetooth(service))

            for characteristic in characteristics:
                cUUID = characteristic.UUID().UUIDString()
                logger.debug("retreiving descriptors for characteristic {}".format(cUUID))
                descriptors = await self.app.central_manager_delegate.connected_peripheral_delegate.discoverDescriptors_(characteristic)

                self.services.add_characteristic(BleakGATTCharacteristicCoreBluetooth(characteristic))
                for descriptor in descriptors:
                    self.services.add_descriptor(
                            BleakGATTDescriptorCoreBluetooth(
                                descriptor, characteristic.UUID().UUIDString()
                                )
                            )
        self._services_resolved = True
        return self.services

    async def read_gatt_char(self, _uuid: str, use_cached=False, **kwargs) -> bytearray:
        """Perform read operation on the specified GATT characteristic.

        Args:
            _uuid (str or UUID): The uuid of the characteristics to read from.
            use_cached (bool): `False` forces macOS to read the value from the
                device again and not use its own cached value. Defaults to `False`.

        Returns:
            (bytearray) The read data.

        """
        _uuid = await self.get_appropriate_uuid(_uuid)
        characteristic = self.services.get_characteristic(_uuid)
        if not characteristic:
            raise BleakError("Characteristic {} was not found!".format(_uuid))

        value = await self.app.central_manager_delegate.connected_peripheral_delegate.readCharacteristic_(characteristic.obj, use_cached=use_cached)
        bytes = value.getBytes_length_(None, len(value))
        return bytearray(bytes)

    async def read_gatt_descriptor(self, handle: int, use_cached=False, **kwargs) -> bytearray:
        """Perform read operation on the specified GATT descriptor.

        Args:
            handle (int): The handle of the descriptor to read from.
            use_cached (bool): `False` forces Windows to read the value from the
                device again and not use its own cached value. Defaults to `False`.

        Returns:
            (bytearray) The read data.
        """
        descriptor = self.services.get_descriptor(handle)
        if not descriptor:
            raise BleakError("Descriptor {} was not found!".format(handle))

        value = await self.app.central_manager_delegate.connected_peripheral_delegate.readDescriptor_(descriptor.obj, use_cached=use_cached)
        bytes = value.getBytes_length_(None, len(value))
        return bytearray(bytes)

    async def write_gatt_char(self, _uuid: str, data: bytearray, response: bool = False) -> None:
        """Perform a write operation of the specified GATT characteristic.

        Args:
            _uuid (str or UUID): The uuid of the characteristics to write to.
            data (bytes or bytearray): The data to send.
            response (bool): If write-with-response operation should be done. Defaults to `False`.

        """
        _uuid = await self.get_appropriate_uuid(_uuid)
        characteristic = self.services.get_characteristic(_uuid)
        if not characteristic:
            raise BleakError("Characteristic {} was not found!".format(_uuid))

        value = NSData.alloc().initWithBytes_length_(data, len(data))
        success = await self.app.central_manager_delegate.connected_peripheral_delegate.writeCharacteristic_value_(characteristic.obj, value)

    async def write_gatt_descriptor(self, handle: int, data: bytearray) -> None:
        """Perform a write operation on the specified GATT descriptor.

        Args:
            handle (int): The handle of the descriptor to read from.
            data (bytes or bytearray): The data to send.

        """
        descriptor = self.services.get_descriptor(handle)
        if not descriptor:
            raise BleakError("Descriptor {} was not found!".format(handle))

        value = NSData.alloc().initWithBytes_length_(data, len(data))
        success = await self.app.central_manager_delegate.connected_peripheral_delegate.writeDescriptor_value_(descriptor.obj, value)

    async def start_notify(self, _uuid: str, callback: Callable[[str, Any], Any], **kwargs) -> None:
        """Activate notifications/indications on a characteristic.

        Callbacks must accept two inputs. The first will be a uuid string
        object and the second will be a bytearray.

        .. code-block:: python

            def callback(sender, data):
                print(f"{sender}: {data}")
            client.start_notify(char_uuid, callback)

        Args:
            _uuid (str or UUID): The uuid of the characteristics to start notification/indication on.
            callback (function): The function to be called on notification.

        """
        _uuid = await self.get_appropriate_uuid(_uuid)
        characteristic = self.services.get_characteristic(_uuid)
        if not characteristic:
            raise BleakError("Characteristic {} not found!".format(_uuid))

        success = await self.app.central_manager_delegate.connected_peripheral_delegate.startNotify_cb_(characteristic.obj, callback)

    async def stop_notify(self, _uuid: str) -> None:
        """Internal method performing call to BleakUWPBridge method.

        Args:
            characteristic_obj: The Managed Windows.Devices.Bluetooth.GenericAttributeProfile.GattCharacteristic Object
            callback: The function to be called on notification.

        Returns:
            (int) The GattCommunicationStatus of the operation.

        """
        _uuid = self.get_appropriate_uuid(_uuid)
        characteristic = self.services.get_characteristic(_uuid)
        if not characteristic:
            raise BleakError("Characteristic {} not found!".format(_uuid))

        success = await self.app.central_manager_delegate.connected_peripheral_delegate.stopNotify_(characteristic.obj)

    async def get_appropriate_uuid(self, _uuid: str) -> str:
        if len(_uuid) == 4:
            return _uuid.upper()

        if await self.is_uuid_16bit_compatible(_uuid):
            return _uuid[4:8].upper()

        return _uuid.upper()

    async def is_uuid_16bit_compatible(self, _uuid: str) -> bool:
        test_uuid = "0000FFFF-0000-1000-8000-00805F9B34FB"
        test_int = await self.convert_uuid_to_int(test_uuid)
        uuid_int = await self.convert_uuid_to_int(_uuid)
        result_int = uuid_int & test_int
        return uuid_int == result_int

    async def convert_uuid_to_int(self, _uuid: str) -> int:
        UUID_cb = CBUUID.alloc().initWithString_(_uuid)
        UUID_data = UUID_cb.data()
        UUID_bytes = UUID_data.getBytes_length_(None, len(UUID_data))
        UUID_int = int.from_bytes(UUID_bytes, byteorder='big')
        return UUID_int

    async def convert_int_to_uuid(self, i: int) -> str:
        UUID_bytes = i.to_bytes(length=16, byteorder='big')
        UUID_data = NSData.alloc().initWithBytes_length_(UUID_bytes, len(UUID_bytes))
        UUID_cb = CBUUID.alloc().initWithData_(UUID_data)
        return UUID_cb.UUIDString()
