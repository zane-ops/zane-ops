from rest_framework.generics import ListCreateAPIView
from .serializers import ComposeStackSerializer


class ComposeStackListAPIView(ListCreateAPIView):
    serializer_class = ComposeStackSerializer
    pagination_class = None
