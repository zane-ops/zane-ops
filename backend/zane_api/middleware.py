from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.conf import settings


class AddCommitShaHeadersMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        response = self.get_response(request)
        if settings.COMMIT_SHA is not None:
            response["X-Commit-Sha"] = settings.COMMIT_SHA
        return response
