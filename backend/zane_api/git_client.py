from typing import Optional
from git import Git, GitCommandError, Repo, Commit


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

    def clone_repository(self, url: str, dest_path: str, branch: str) -> Repo:
        try:
            return Repo.clone_from(url, dest_path, branch=branch)
        except GitCommandError as e:
            raise GitCloneFailedError(e.command, e.status, e.stderr, e.stdout) from e

    def checkout_repository(self, repo: Repo, commit_sha: str) -> Commit:
        try:
            repo.git.checkout(commit_sha)
            return repo.commit(commit_sha)
        except GitCommandError as e:
            raise GitCheckoutFailedError(e.command, e.status, e.stderr, e.stdout) from e
