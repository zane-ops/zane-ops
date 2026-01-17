import asyncio
import os
import signal
from typing import Any, Optional, Protocol, Tuple
from asyncio.subprocess import Process

from .utils import Colors


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
        self._terminate_task: Optional[asyncio.Task[int]] = None
        self._cancellation_requested = False

    async def run(self) -> Tuple[int | None, Optional[Any]]:
        print(
            f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}]: Running shell command {Colors.YELLOW}{self.command}{Colors.ENDC}"
        )
        process = await asyncio.create_subprocess_shell(
            self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            # The os.setsid() is passed in the argument preexec_fn so
            # it's run after the fork() and before  exec() to run the shell.
            # ref: https://stackoverflow.com/a/4791612/10322846
            preexec_fn=os.setsid,
        )

        # Start a task to monitor the cancel event
        cancel_monitor_task = asyncio.create_task(self._monitor_cancel_event(process))

        try:
            # Continue processing output until EOF is reached
            while not await self._process_output(process):
                continue
        except asyncio.CancelledError:
            if self._terminate_task is None:
                self._terminate_task = asyncio.create_task(self._terminate(process))
            # Continue collecting logs even after cancellation
            while process.returncode is None:
                if await self._process_output(process, ignore_cancel=True):
                    break
            raise
        finally:
            # Cancel the monitor task
            cancel_monitor_task.cancel()
            try:
                await cancel_monitor_task
            except asyncio.CancelledError:
                pass

            if self.exit_code is None:
                self.exit_code = await (
                    process.wait()
                    if self._terminate_task is None
                    else self._terminate_task
                )

        exit_color = Colors.GREEN if self.exit_code == 0 else Colors.RED
        print(
            f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}] Process finished with exit_code={exit_color}{self.exit_code}{Colors.ENDC}"
        )
        return (self.exit_code, self.result)

    async def _monitor_cancel_event(self, process: Process):
        """Monitor the cancel event and initiate termination when triggered"""
        await self.cancel_event.wait()
        if process.returncode is None:
            self._cancellation_requested = True
            print(
                f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}] {Colors.RED}Received cancel_event{Colors.ENDC}"
            )
            await self.output_handler(
                f"{Colors.YELLOW}{self.operation_name}{Colors.ENDC} operation cancelled. Collecting remaining logs..."
            )
            self._terminate_task = asyncio.create_task(self._terminate(process))

    async def _process_output(
        self, process: Process, ignore_cancel: bool = False
    ) -> bool:
        """Returns True if EOF reached"""
        if process.stdout is None:
            return True

        try:
            stdout = await read_until(process.stdout, delimiters=[b"\r", b"\n"])

            if not stdout:
                print(
                    f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}] Reached {Colors.GREY}EOF{Colors.ENDC}"
                )
                return True

            if stdout:
                result = await self.output_handler(stdout.decode().rstrip())
                if result is not None:
                    self.result = result

            return False
        except asyncio.CancelledError:
            if ignore_cancel:
                # Continue processing if we're supposed to ignore cancellation
                return False
            raise

    async def _terminate(self, process: Process) -> int:
        if process.returncode is not None:
            return process.returncode

        # stop with SIGINT, to allow for graceful shutdown
        # ref: https://claude.ai/share/47c662bd-55e4-483f-97a5-1cdaaa974384
        print(
            f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}] Sending signal {Colors.ORANGE}SIGINT{Colors.ENDC} to the process group..."
        )
        os.killpg(os.getpgid(process.pid), signal.SIGINT)
        exit_code = await process.wait()
        print(
            f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}] Process terminated with code {Colors.ORANGE}{exit_code}{Colors.ENDC}"
        )
        return exit_code
