"""
Base clase for backend servers.

Created on 2019-07-03 by kevincar <kevincarrolldavis@gmail.com>

"""

import abc
import asyncio
from asyncio import AbstractEventLoop

from bleak.backends.service import BleakGATTServiceCollection, BleakGATTService

class BaseBleakServer(abc.ABC):
    """
    The Server Interface for Bleak Backend
    """

    def __init__(self, loop: AbstractEventLoop = None, **kwargs):
        self.loop = loop if loop else asyncio.get_event_loop()

        self.services = BleakGATTServiceCollection()

    # Async Context managers

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    @abc.abstractmethod
    async def start(self, **kwargs) -> bool:
        """
        Start the server

        Returns:
            Boolean - Whether server started successfully
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def stop(self) -> bool:
        """
        Stop the server

        Returns:
            Boolean - Whether the server stopped successfully
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def is_connected(self) -> bool:
        """
        Determine whether there are any connected peripheral devices
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def is_advertising(self) -> bool:
        """
        Determine whether the server is advertising
        """

    @abc.abstractmethod
    async def add_service(self, service: BleakGATTService):
        raise NotImplementedError()
