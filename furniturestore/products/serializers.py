from rest_framework import serializers

from .models import (
    Category,
    Products,
    CatalogModel,
    LandingPage,
    BannerImageModel,
    LandingPageBanner
)


class CategoryListSerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "name_eng",
            "description",
            "description_eng",
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


class LandingPageBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandingPageBanner
        fields = (
            "id",
            "image_url",
            "public_id",
            "alt_text",
            "is_primary",
        )


class LandingPageListSerializer(serializers.ModelSerializer):
    banners = serializers.SerializerMethodField()

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
            "banners",
        )

    def get_banners(self, obj):
        if obj.section_key == "triple_section":
            active_banners = obj.banners.filter(is_deleted=False)
            return LandingPageBannerSerializer(active_banners, many=True).data
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.section_key != "triple_section":
            representation.pop("banners", None)
        return representation

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
            "link_url",
            "is_primary",
            "created_at",
        ]