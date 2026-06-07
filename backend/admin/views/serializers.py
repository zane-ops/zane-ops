from rest_framework import pagination


class InstanceUserPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "per_page"
    page_query_param = "page"
