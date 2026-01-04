from rest_framework import serializers

from .models import (
    Category,
    ProductImage,
    Products,
)

from decimal import Decimal
from django.db.models.functions import Coalesce
from django.db.models import Sum

class CategoryListSerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "description",
            "slug",
            "is_deleted",
            "created_at",
            "product_count",
            "image_url"
        ]


class CategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")


    

class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta:
        model = Products
        fields = [
            "id",
            "name",
            "description",
            "created_at",
            "updated_at",
            "category_name",
            "images",
            "product_type",
            "stock",
            "stock_code",
        ]

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_images(self, obj):
        imgs = obj.images.filter(is_deleted=False)
        return [{"url": i.image_url} for i in imgs if i.image_url]
    
class ProjectListSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()

    class Meta:
        model = Products
        fields = [
            "id",
            "name",
            "created_at",
            "updated_at",
            "images",
        ]

    def get_images(self, obj):
        imgs = obj.images.filter(is_deleted=False)
        return [{"url": i.image_url} for i in imgs if i.image_url]