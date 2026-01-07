from rest_framework import serializers

from .models import (
    Category,
    Products,
    CatalogModel,
    LandingPage,
    BannerImageModel
)


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
            "for_project"
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


class CatalogSerializer(serializers.ModelSerializer):
    pdf_url = serializers.SerializerMethodField()
    cover_image_url = serializers.ReadOnlyField(source='url')

    class Meta:
        model = CatalogModel
        fields = ["id", "name", "cover_image_url", "pdf_url", "created_at"]

    def get_pdf_url(self, obj):
        if obj.pdf_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.pdf_file.url)
            return obj.pdf_file.url
        return None
    
    

ALLOWED_FONTS = {
    "inter",
    "poppins",
    "montserrat",
    "manrope",
    "dm-sans",
    "nunito-sans",
    "playfair",
    "lora",
    "merriweather",
    "cormorant-garamond",
}


class LandingPageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandingPage
        fields = (
            "id",
            "section_key",
            "title",
            "description",
            "image_url",
            "public_id",
            "title_font_family",
            "font_family",
            "title_en",
            "description_en",
        )

    def validate_title_font_family(self, value):
        if value and value not in ALLOWED_FONTS:
            raise serializers.ValidationError("Geçersiz yazı tipi değeri.")
        return value

    def validate_font_family(self, value):
        if value and value not in ALLOWED_FONTS:
            raise serializers.ValidationError("Geçersiz yazı tipi değeri.")
        return value
    


class BannerImageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BannerImageModel
        fields = [
            "id",
            "image_url",
            "alt_text",
            "public_id",
            "is_primary",
            "created_at",
        ]