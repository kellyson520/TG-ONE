import asyncio
import logging
from typing import List, Optional, Callable
from telethon import TelegramClient

logger = logging.getLogger(__name__)

class ClientPool:
    """
    Telethon Client Pool
    Manages a pool of TelegramClient instances to distribute load.
    Currently wraps a single client but allows for future expansion (e.g. multiple sessions).
    """
    _instance: Optional["ClientPool"] = None

    def __init__(self):
        self._clients: List[TelegramClient] = []
        self._lock = asyncio.Lock()
        self._index = 0

    @classmethod
    def get_instance(cls) -> "ClientPool":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    def add_client(self, client: TelegramClient):
        """Add a client to the pool"""
        if client and client not in self._clients:
            self._clients.append(client)
            logger.info(f"Client added to pool (Total: {len(self._clients)})")

    async def get_client(self) -> TelegramClient:
        """Get a client from the pool (Round Robin strategy)"""
        async with self._lock:
            if not self._clients:
                raise RuntimeError("No clients available in ClientPool")
            
            # Simple Round Robin
            client = self._clients[self._index]
            self._index = (self._index + 1) % len(self._clients)
            
            # Check if connected?
            if not client.is_connected():
                # Try next?
                # For now just return it, reconnection is handled by client internally usually.
                pass
                
            return client
            
    def get_all_clients(self) -> List[TelegramClient]:
        """Return all clients"""
        return list(self._clients)

    async def broadcast(self, func: Callable, *args, **kwargs):
        """Execute a function on all clients"""
        tasks = []
        for client in self._clients:
            if asyncio.iscoroutinefunction(func):
                 tasks.append(func(client, *args, **kwargs))
            else:
                 tasks.append(asyncio.to_thread(func, client, *args, **kwargs))
        return await asyncio.gather(*tasks, return_exceptions=True)

# Global Instance
client_pool = ClientPool.get_instance()
