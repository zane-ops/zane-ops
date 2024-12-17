from typing import Callable
from django.http import HttpRequest, HttpResponse
import os


class AddCommitShaHeadersMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        response = self.get_response(request)
        COMMIT_SHA = os.environ.get("COMMIT_SHA", None)
        if COMMIT_SHA is not None:
            response["X-Commit-Sha"] = COMMIT_SHA
        return response
