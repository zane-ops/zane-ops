import asyncio
from typing import Callable, Coroutine

from adrf.generics import ListAPIView, CreateAPIView  # , ListCreateAPIView
from asgiref.sync import sync_to_async
from django.db import transaction
from django.db.models import QuerySet
from rest_framework import status
from rest_framework.response import Response


async def get_data(serializer):
    """Use adata if the serializer supports it, data otherwise."""
    return await serializer.adata if hasattr(serializer, "adata") else serializer.data


class AsyncListAPIView(ListAPIView):
    async def apaginate_queryset(self, queryset: QuerySet):
        """
        Return a single page of results, or `None` if pagination is disabled.
        """
        if self.paginator is None:
            return None
        if asyncio.iscoroutinefunction(self.paginator.paginate_queryset):
            return await self.paginator.paginate_queryset(
                queryset, self.request, view=self
            )
        return await sync_to_async(self.paginator.paginate_queryset)(
            queryset, self.request, view=self
        )

    async def alist(self, *args, **kwargs):
        queryset = self.filter_queryset(await self.get_queryset())

        page = await self.apaginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = await get_data(serializer)
            return await self.get_apaginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        data = await get_data(serializer)
        return Response(data, status=status.HTTP_200_OK)


class AsyncCreateAPIView(CreateAPIView):
    async def perform_acreate(self, serializer):
        return await (
            serializer.asave
            if hasattr(serializer, "asave")
            else sync_to_async(serializer.save)
        )()

    async def post(self, request, *args, **kwargs):
        if asyncio.iscoroutinefunction(self.acreate):
            return await self.acreate(request, *args, **kwargs)
        return await sync_to_async(self.acreate)(request, *args, **kwargs)


class AsyncAtomic:
    def __init__(self):
        self.atomic = transaction.atomic()

    async def __aenter__(self):
        await sync_to_async(self.atomic.__enter__)()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            await sync_to_async(self.atomic.__exit__)(exc_type, exc, tb)
        else:
            await sync_to_async(self.atomic.__exit__)(None, None, None)

    async def on_commit(self, func: Callable | Coroutine):
        fn = func
        if asyncio.iscoroutinefunction(func):
            fn = lambda: asyncio.run(func())
        if asyncio.iscoroutine(func):
            fn = lambda: asyncio.run(func)

        await sync_to_async(transaction.on_commit)(fn)
