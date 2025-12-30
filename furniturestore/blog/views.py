from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from blog.models import Blog
from products.pagination import Pagination10

class BlogCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        title = (request.data.get("title") or "").strip()
        description = (request.data.get("description") or "").strip()

        if not title:
            return Response(
                {"status": 400, "message": "title zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(description) > 4000:
            return Response(
                {"status": 400, "message": "description en fazla 4000 karakter olabilir."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        blog = Blog.objects.create(
            title=title,
            description=description or None,
        )

        return Response(
            {
                "status": 201,
                "data": {
                    "id": blog.id,
                    "title": blog.title,
                    "description": blog.description,
                    "created_at": blog.created_at,
                    "updated_at": blog.updated_at,
                    "is_deleted": blog.is_deleted,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class BlogListAPIView(APIView):
    pagination_class = Pagination10

    def get(self, request, *args, **kwargs):
        title_q = (request.query_params.get("title") or "").strip()
        order_q = (request.query_params.get("order") or "desc").strip().lower()

        qs = Blog.objects.filter(is_deleted=False)

        if title_q:
            qs = qs.filter(title__icontains=title_q)

        if order_q == "asc":
            qs = qs.order_by("id")
        else:
            qs = qs.order_by("-id")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)

        results = [
            {
                "id": blog.id,
                "title": blog.title,
                "description": blog.description,
                "created_at": blog.created_at,
                "updated_at": blog.updated_at,
            }
            for blog in page
        ]

        paginated = paginator.get_paginated_response(results)
        paginated.data["status"] = 200
        return paginated


class BlogDetailAPIView(APIView):

    def get(self, request, id, *args, **kwargs):
        try:
            blog = Blog.objects.get(id=id, is_deleted=False)
        except Blog.DoesNotExist:
            return Response(
                {"status": 404, "message": "Blog bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "status": 200,
                "data": {
                    "id": blog.id,
                    "title": blog.title,
                    "description": blog.description,
                    "created_at": blog.created_at,
                    "updated_at": blog.updated_at,
                },
            },
            status=status.HTTP_200_OK,
        )
    
    @transaction.atomic
    def patch(self, request, id, *args, **kwargs):
        try:
            blog = Blog.objects.get(id=id, is_deleted=False)
        except Blog.DoesNotExist:
            return Response(
                {"status": 404, "message": "Blog bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data_in = request.data

        is_del = data_in.get("is_deleted")
        if is_del is True or (isinstance(is_del, str) and str(is_del).lower() == "true"):
            blog.is_deleted = True
            blog.save(update_fields=["is_deleted"])

            return Response(
                {"status": 200, "message": "Blog silindi."},
                status=status.HTTP_200_OK,
            )

        if "title" in data_in:
            title = (data_in.get("title") or "").strip()
            if not title:
                return Response(
                    {"status": 400, "message": "title boş olamaz."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            blog.title = title

        if "description" in data_in:
            description = (data_in.get("description") or "").strip()
            blog.description = description or None

        blog.save()

        return Response(
            {
                "status": 200,
                "data": {
                    "id": blog.id,
                    "title": blog.title,
                    "description": blog.description,
                    "created_at": blog.created_at,
                    "updated_at": blog.updated_at,
                    "is_deleted": blog.is_deleted,
                },
            },
            status=status.HTTP_200_OK,
        )