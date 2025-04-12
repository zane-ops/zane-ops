import asyncio
import os
import signal
from typing import Any, Awaitable, Optional, Protocol, Tuple
from asyncio.subprocess import Process
from .utils import Colors, async_noop


class OutputHandlerFunction(Protocol):
    async def __call__(self, message: str, error: bool = False) -> Any: ...


class AyncSubProcessRunner:
    SIGTERM_EXIT_CODE = 130

    def __init__(
        self,
        command: str,
        cancel_event: Optional[asyncio.Event],
        output_handler: OutputHandlerFunction,
        operation_name: str,
    ):
        self.command = command
        self.cancel_event = cancel_event
        self.output_handler = output_handler
        self.operation_name = operation_name
        self.result: Any = None

    async def run(self) -> Tuple[int, Optional[Any]]:
        process = await asyncio.create_subprocess_shell(
            self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=os.setsid,  # set session ID
        )

        try:
            while True:
                if await self._process_output(process):
                    break
        except asyncio.CancelledError:
            await self._terminate(process)
            raise
        finally:
            if self.exit_code is None:
                self.exit_code = await process.wait()

        return (self.exit_code, self.result)

    @staticmethod
    async def _read_until(stream: asyncio.StreamReader, delimiters: list[bytes]):
        """
        Custom replacement for `asyncio.StreamReader.readuntil`
        accepting multiple delimiters instead of one.
        Plus it doesn't throw an error if the end data doesn't have
        the delimiter character.
        """
        buffer = bytearray()
        while True:
            character = await stream.read(1)
            if not character:
                break
            buffer.extend(character)
            if character in delimiters:
                break
        return bytes(buffer)

    async def _read_stream(self, stream: asyncio.StreamReader | None):
        """Default stream reader implementation"""
        return (
            await self._read_until(stream, delimiters=[b"\r", b"\n"])
            if stream
            else None
        )

    async def _read_process_output(self, process: Process):
        return await asyncio.gather(
            self._read_stream(process.stdout),
            self._read_stream(process.stderr),
        )

    async def _process_output(self, process: Process) -> bool:
        """Returns True if EOF reached or cancellation requested"""
        read_streams_task = asyncio.create_task(self._read_process_output(process))

        cancel_task = asyncio.create_task(
            self.cancel_event.wait() if self.cancel_event else async_noop()
        )

        done, _ = await asyncio.wait(
            [read_streams_task, cancel_task], return_when=asyncio.FIRST_COMPLETED
        )

        if read_streams_task in done:
            stdout, stderr = await read_streams_task
            cancel_task.cancel()
        else:
            if self.cancel_event and self.cancel_event.is_set():
                await self._terminate(process)
                read_streams_task.cancel()

                print(
                    f"{Colors.RED}Received cancel_event: {self.cancel_event} {Colors.ENDC}"
                )
                await self.output_handler(
                    f"{Colors.YELLOW}{self.operation_name}{Colors.ENDC} operation cancelled."
                )
                return True
            else:
                stdout, stderr = await read_streams_task

        if stdout or stderr:
            if stdout:
                result = await self.output_handler(stdout.decode().rstrip())
                if result is not None:
                    self.result = result
            if stderr:
                await self.output_handler(stderr.decode().rstrip(), error=True)
        else:
            print("Reached EOF")
            return True

        return False

    async def _terminate(self, process: Process) -> None:
        if process.returncode is None:
            process.terminate()
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            self.exit_code = await process.wait()
