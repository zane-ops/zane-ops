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

    async def run(self) -> Tuple[int | None, Optional[Any]]:
        process = await asyncio.create_subprocess_shell(
            self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            # The os.setsid() is passed in the argument preexec_fn so
            # it's run after the fork() and before  exec() to run the shell.
            # ref: https://stackoverflow.com/a/4791612/10322846
            # preexec_fn=os.setsid,
        )

        try:
            while not await self._process_output(process):
                continue
        except asyncio.CancelledError:
            if self._terminate_task is None:
                self._terminate_task = asyncio.create_task(self._terminate(process))
            raise
        finally:
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
                read_output_task.cancel()
                self._terminate_task = asyncio.create_task(self._terminate(process))

                print(
                    f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}] {Colors.RED}Received cancel_event: {self.cancel_event} {Colors.ENDC}"
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

    async def _terminate(self, process: Process) -> int:
        if process.returncode is not None:
            return process.returncode

        # ref: https://chatgpt.com/share/68046f8b-e5f0-8007-ba09-958b0b3d8612
        # send SIGTERM first, to allow for graceful shutdown
        print(
            f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}] Sending signal {Colors.ORANGE}SIGTERM{Colors.ENDC} to the process..."
        )
        # process.send_signal(signal.SIGTERM)
        process.terminate()
        try:
            print(
                f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}] Waiting for process to be finished (timeout=5s)..."
            )
            exit_code = await asyncio.wait_for(process.wait(), timeout=5)

        except asyncio.TimeoutError:
            print(
                f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}] Process failed to be killed in the timeout, escalading to {Colors.RED}SIGTERM{Colors.ENDC} on the whole process group..."
            )
            # escalate to SIGTERM on the whole process group if it fails the timeout
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGTERM)
            print(
                f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}] Waiting for the whole process group to be terminated..."
            )
            exit_code = await process.wait()
        print(
            f"[{Colors.YELLOW}{self.operation_name}{Colors.ENDC}] Process finished with code {Colors.ORANGE}{exit_code}{Colors.ENDC}"
        )
        return exit_code

        # if process.returncode is None:
        #     print(
        #         f"Killing process for operation... {Colors.YELLOW}{self.operation_name}{Colors.ENDC}"
        #     )
        #     process.kill()
        # print("Waiting for process to be cleaned up...")
        # exit_code = await process.wait()
        # print(f"Process exited with code {Colors.ORANGE}{exit_code}{Colors.ENDC}")
        # return exit_code
