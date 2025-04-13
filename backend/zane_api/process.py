import asyncio
from typing import Any, Optional, Protocol, Tuple
from asyncio.subprocess import Process

from .utils import Colors


# from .utils import Colors, async_noop
async def async_noop():
    """This function does nothing"""
    ...


async def read_until(stream: asyncio.StreamReader, delimiters: list[bytes]):
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


class OutputHandlerFunction(Protocol):
    async def __call__(self, message: str) -> Any: ...


class AyncSubProcessRunner:

    def __init__(
        self,
        command: str,
        cancel_event: asyncio.Event,
        output_handler: OutputHandlerFunction,
        operation_name: str,
    ):
        self.command = command
        self.cancel_event = cancel_event
        self.output_handler = output_handler
        self.operation_name = operation_name
        self.result: Any = None
        self.exit_code: Optional[int] = None

    async def run(self) -> Tuple[int | None, Optional[Any]]:
        print(
            f"Running process shell with command {Colors.YELLOW}{self.command}{Colors.ENDC}"
        )
        process = await asyncio.create_subprocess_exec(
            *self.command.split(" "),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        try:
            while not await self._process_output(process):
                continue
        except asyncio.CancelledError:
            await self._terminate(process)
            raise
        finally:
            if self.exit_code is None:
                self.exit_code = await process.wait()

        return (self.exit_code, self.result)

    async def _process_output(self, process: Process) -> bool:
        """Returns True if EOF reached or cancellation requested"""
        read_output_task = asyncio.create_task(
            read_until(process.stdout, delimiters=[b"\r", b"\n"])
            if process.stdout
            else async_noop()
        )

        cancel_task = asyncio.create_task(self.cancel_event.wait())

        done, _ = await asyncio.wait(
            [read_output_task, cancel_task], return_when=asyncio.FIRST_COMPLETED
        )

        if read_output_task in done:
            stdout = await read_output_task
            cancel_task.cancel()
        else:
            if self.cancel_event and self.cancel_event.is_set():
                await self._terminate(process)
                read_output_task.cancel()

                print(
                    f"{Colors.RED}Received cancel_event: {self.cancel_event} {Colors.ENDC}"
                )
                await self.output_handler(
                    f"{Colors.YELLOW}{self.operation_name}{Colors.ENDC} operation cancelled."
                )
                return True
            else:
                stdout = await read_output_task

        if stdout:
            if stdout:
                result = await self.output_handler(stdout.decode().rstrip())
                if result is not None:
                    self.result = result
        else:
            print(f"Reached {Colors.GREY}EOF{Colors.ENDC}")
            return True

        return False

    async def _terminate(self, process: Process) -> None:
        if process.returncode is None:
            process.terminate()
            self.exit_code = await process.wait()
