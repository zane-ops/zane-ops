import asyncio
from django.core.cache import cache
from asgiref.sync import sync_to_async
from datetime import timedelta


class AsyncSemaphore:
    def __init__(
        self,
        key: str,
        limit=1,
        semaphore_timeout=timedelta(seconds=10),
        lock_timeout=timedelta(seconds=5),
    ):
        self.key = f"[zaneops::internal::semaphore_{key}]"
        self.lock_key = f"{self.key}:lock"
        self.limit = limit
        self.semaphore_timeout = semaphore_timeout.seconds
        self.lock_timeout = lock_timeout.seconds

    async def _acquire_lock(self):
        return await sync_to_async(cache.add)(self.lock_key, "1", self.lock_timeout)

    async def _release_lock(self):
        await sync_to_async(cache.delete)(self.lock_key)

    async def acquire(self, retry_delay=0.1, max_retries: int | None = None):
        retries = 0
        while max_retries is None or retries < max_retries:
            if await self._acquire_lock():
                try:
                    count = await sync_to_async(cache.get)(self.key, 0)
                    if count < self.limit:
                        await sync_to_async(cache.set)(
                            self.key, count + 1, self.semaphore_timeout
                        )
                        return True
                finally:
                    await self._release_lock()
            retries += 1
            await asyncio.sleep(retry_delay)
        return False

    async def release(self):
        if await self._acquire_lock():
            try:
                count = await sync_to_async(cache.get)(self.key, 0)
                if count > 0:
                    await sync_to_async(cache.set)(
                        self.key, count - 1, self.semaphore_timeout
                    )
            finally:
                await self._release_lock()

    async def reset(self, retry_delay=0.1):
        """
        Reset the semaphore by setting its counter to 0, effectively releasing all acquired slots.
        This method uses the same lock mechanism to ensure an atomic update.
        """
        while True:
            if await self._acquire_lock():
                try:
                    await sync_to_async(cache.set)(self.key, 0, self.semaphore_timeout)
                    return
                finally:
                    await self._release_lock()
            await asyncio.sleep(retry_delay)

    async def acquire_all(self, retry_delay=0.1, max_retries: int | None = None):
        """
        Wait until the semaphore is completely free and then acquire all available slots.
        This method sets the counter to the full limit, effectively blocking any other acquirer.
        """
        retries = 0
        while max_retries is None or retries < max_retries:
            if await self._acquire_lock():
                try:
                    count: int = await sync_to_async(cache.get)(self.key, 0)
                    if count == 0:
                        # Acquire all tokens at once.
                        await sync_to_async(cache.set)(
                            self.key, self.limit, self.semaphore_timeout
                        )
                        return True
                finally:
                    await self._release_lock()
            retries += 1
            await asyncio.sleep(retry_delay)
        return False

    async def __aenter__(self):
        acquired = await self.acquire()
        if not acquired:
            raise Exception("Failed to acquire semaphore")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()
