from dataclasses import dataclass


@dataclass
class GitCommitInfo:
    sha: str
    message: str
    author_name: str
