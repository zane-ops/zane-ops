from dataclasses import dataclass
from typing import Optional


@dataclass
class GitCommitInfo:
    sha: str
    message: Optional[str]
    author_name: Optional[str]
