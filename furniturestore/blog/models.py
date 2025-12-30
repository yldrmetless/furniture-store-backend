from django.db import models


class Blog(models.Model):
    title = models.CharField(max_length=255, null=True, blank=True)

    description = models.CharField(max_length=4000, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    is_deleted = models.BooleanField(default=False)