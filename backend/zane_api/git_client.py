from typing import Callable, List, Optional
from git import Git, GitCommandError, RemoteProgress, Repo, Commit
import asyncio
from .utils import Colors
from .process import AyncSubProcessRunner, OutputHandlerFunction


class GitCloneFailedError(GitCommandError):
    pass


class GitCheckoutFailedError(GitCommandError):
    pass


class GitClient:
    def __init__(self):
        self._git = Git()

    def check_if_git_repository_is_valid(
        self, url: str, branch: Optional[str] = None
    ) -> bool:
        """
        Check if a git repository exists and that the provided branch also exist within the repository
        """
        try:
            refs = self._git.ls_remote("--heads", url, branch)
            return bool(refs.strip())
        except GitCommandError:
            return False

    def resolve_commit_sha_for_branch(self, url: str, branch: str) -> Optional[str]:
        """
        Get the latest commit SHA for a given branch in a remote Git repository.
        """
        try:
            refs: str = self._git.ls_remote("--heads", url, branch)
            for line in refs.splitlines():
                sha, ref = line.split()
                if ref.endswith(f"refs/heads/{branch}"):
                    return sha
            return None
        except GitCommandError:
            return None

    def list_branches_for_repository(self, url: str) -> List[str]:
        """
        Get the latest commit SHA for a given branch in a remote Git repository.
        """
        branches: List[str] = []
        try:
            refs: str = self._git.ls_remote("--heads", url)
            for line in refs.splitlines():
                sha, ref = line.split()
                branches.append(ref.replace("refs/heads/", ""))
        except GitCommandError:
            pass
        return branches

    def clone_repository(
        self,
        url: str,
        dest_path: str,
        branch: str,
        clone_progress_handler: Callable[[str], None] | None = None,
    ) -> Repo:
        try:
            progress_handler = None
            if clone_progress_handler is not None:
                progress_handler = SimpleRichCloneProgressWithMessageHandler(
                    message_handler=clone_progress_handler
                )
            return Repo.clone_from(
                url, dest_path, branch=branch, progress=progress_handler  # type: ignore
            )
        except GitCommandError as e:
            raise GitCloneFailedError(e.command, e.status, e.stderr, e.stdout) from e

    async def aclone_repository(
        self,
        url: str,
        dest_path: str,
        branch: str,
        message_handler: OutputHandlerFunction,
        cancel_event: asyncio.Event,
    ) -> Repo:
        git_clone_command = f"/usr/bin/git clone --progress --single-branch --branch {branch} {url} {dest_path}"
        await message_handler(
            f"Running {Colors.YELLOW}{git_clone_command}{Colors.ENDC}"
        )
        runner = AyncSubProcessRunner(
            command=git_clone_command,
            cancel_event=cancel_event,
            operation_name="git clone",
            output_handler=message_handler,
        )
        exit_code, _ = await runner.run()
        print(
            f"Process finished with exit_code={Colors.ORANGE}{exit_code}{Colors.ENDC}"
        )
        if exit_code != 0:
            raise GitCloneFailedError(git_clone_command, exit_code)
        else:
            return Repo(dest_path)

    def checkout_repository(self, repo: Repo, commit_sha: str) -> Commit:
        try:
            repo.git.checkout(commit_sha)
            return repo.commit(commit_sha)
        except GitCommandError as e:
            raise GitCheckoutFailedError(e.command, e.status, e.stderr, e.stdout) from e


class SimpleRichCloneProgressWithMessageHandler(RemoteProgress):
    OP_CODES = [
        "BEGIN",
        "CHECKING_OUT",
        "COMPRESSING",
        "COUNTING",
        "END",
        "FINDING_SOURCES",
        "RECEIVING",
        "RESOLVING",
        "WRITING",
    ]
    OP_CODE_MAP = {getattr(RemoteProgress, _op_code): _op_code for _op_code in OP_CODES}

    def __init__(self, message_handler: Callable[[str], None]) -> None:
        """
        Initialize a clone progress handler that uses a custom message handler.

        Args:
            message_handler: A function that takes a message string and does something with it
        """
        super().__init__()
        self.message_handler = message_handler
        self.curr_op = ""
        self.current_total = 0
        self.current_count = 0

    def close(self):
        pass  # No resources to clean up

    def __del__(self) -> None:
        pass  # No resources to clean up

    @classmethod
    def get_curr_op(cls, op_code: int) -> str:
        """Get OP name from OP code."""
        # Remove BEGIN- and END-flag and get op name
        op_code_masked = op_code & cls.OP_MASK
        return cls.OP_CODE_MAP.get(op_code_masked, "?").title()

    def update(
        self,
        op_code: int,
        cur_count: str | float,
        max_count: str | float | None = None,
        message: str | None = "",
    ) -> None:
        # Start new operation on each BEGIN-flag
        if op_code & self.BEGIN:
            self.curr_op = self.get_curr_op(op_code)
            self.current_total = float(max_count or 100)
            self.current_count = 0
            if self.curr_op == "Counting":
                self.message_handler("")
            self.message_handler(f"⏱️ Started {self.curr_op}: {message}")

        # Update progress
        if cur_count is not None:
            self.current_count = float(cur_count)
            # Calculate percentage
            if self.current_total > 0:
                percent = min(100, int((self.current_count / self.current_total) * 100))
                progress_bar = self._get_progress_bar(percent)
                self.message_handler(
                    f"📊 {self.curr_op}: {progress_bar} {str(str(percent) + '%').ljust(4)} | {message or ''}"
                )

        # End progress monitoring on each END-flag
        if op_code & self.END:
            self.message_handler(f"✅ Completed {self.curr_op}: {message or 'Done!'}")
            self.message_handler("")

    def _get_progress_bar(self, percent: int) -> str:
        """Generate a text-based progress bar."""
        width = 20
        filled = int(width * percent / 100)
        return f"[{'=' * filled}{' ' * (width - filled)}]"
