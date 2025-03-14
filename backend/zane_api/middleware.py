from typing import Callable
from django.http import HttpRequest, HttpResponse
import os
from django.conf import settings
import logging

# Get the logger for this module
logger = logging.getLogger(__name__)


class AddCommitShaHeadersMiddleware:
    """
    Middleware to add the current commit SHA to the response headers.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """
        Initializes the middleware with the next callable in the chain.
        """
        if not callable(get_response):
            raise TypeError("get_response must be a callable object")
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Processes each request to add the commit SHA header to the response.
        """
        response: HttpResponse = self.get_response(request)  # Ensure correct type hinting

        # Check if COMMIT_SHA is defined and is a string before adding the header
        commit_sha = getattr(settings, "COMMIT_SHA", None)
        if isinstance(commit_sha, str) and commit_sha:  # Check if it's a non-empty string
            response["X-Commit-Sha"] = commit_sha
        elif commit_sha is not None:
            logger.warning(
                "COMMIT_SHA is defined but is not a string.  Header X-Commit-Sha will not be added."
            )
        else:
            logger.debug("COMMIT_SHA is not defined in settings. Header X-Commit-Sha will not be added.")

        return response
