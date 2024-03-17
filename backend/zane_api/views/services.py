from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class DockerServiceAPIView(APIView):
    def post(self, request: Request, project_slug: str):
        return Response()
