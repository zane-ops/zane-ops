from typing import Optional
from git import Git, GitCommandError


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
