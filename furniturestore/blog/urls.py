from django.urls import path

from blog.views import (
    BlogCreateAPIView,
    BlogDetailAPIView,
    BlogListAPIView
)

urlpatterns = [
    path("create-blog/", BlogCreateAPIView.as_view(), name="create-blog"),

    path("blog-list/", BlogListAPIView.as_view(), name="blog-list"),

    path("blog-detail/<int:id>", BlogDetailAPIView.as_view(), name="blog-detail"),
]
