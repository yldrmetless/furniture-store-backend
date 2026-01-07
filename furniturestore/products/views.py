
import os
import cloudinary.uploader
from django.db import transaction
from django.utils.text import slugify
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from products.serializers import ProductListSerializer,ProjectListSerializer,CatalogSerializer,LandingPageListSerializer, BannerImageListSerializer
from django.db.models import Prefetch
from django.db.models import Count, Q
from urllib.parse import unquote_plus
from django.db.models.functions import Lower, Replace
from django.db.models import Value

import os
from django.conf import settings
from products.models import (
    Category,
    ProductImage,
    Products,
    ReferenceImage,
    ReferenceModel,
    ReferenceCategory,
    CatalogModel,
    LandingPage,
    BannerImageModel,
    Banner
)
from products.pagination import Pagination10
from products.serializers import (
    CategoryListSerializer,
)
from django.db import IntegrityError


class CategoryCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        name = request.data.get("name")
        description = request.data.get("description")
        image_url = request.data.get("image_url")
        public_id = request.data.get("public_id")

        if not name:
            return Response(
                {"status": 400, "message": "Kategori adı zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slug = slugify(name)
        base_slug = slug
        counter = 1

        while Category.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        category = Category.objects.create(
            name=name,
            description=description or "",
            slug=slug,
            image_url=image_url or None,
            public_id=public_id or None,
        )

        return Response(
            {
                "status": 201,
                "data": {
                    "id": category.id,
                    "name": category.name,
                    "description": category.description,
                    "slug": category.slug,
                    "is_deleted": category.is_deleted,
                    "created_at": category.created_at,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class CategoryListAPIView(ListAPIView):
    pagination_class = Pagination10

    def get(self, request, *args, **kwargs):
        qs = (
            Category.objects.filter(is_deleted=False)
            .annotate(
                product_count=Count(
                    "products",
                    filter=Q(products__is_deleted=False),
                )
            )
        )

        name = (request.query_params.get("name") or "").strip()
        if name:
            qs = qs.filter(name__icontains=name)

        order_by = (request.query_params.get("order_by") or "desc").lower()
        if order_by == "asc":
            qs = qs.order_by("created_at", "id")
        else:
            qs = qs.order_by("-created_at", "-id")

        page = self.paginate_queryset(qs)
        serializer = CategoryListSerializer(page, many=True, context={"request": request})
        paginated_data = self.get_paginated_response(serializer.data).data

        return Response(
            {
                "status": 200,
                **paginated_data,
            },
            status=200,
        )


class CategoryDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        try:
            category = Category.objects.get(id=id, is_deleted=False)
        except Category.DoesNotExist:
            return Response(
                {"status": 404, "detail": "Kategori bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CategoryListSerializer(category, context={"request": request})

        return Response(
            {
                "status": 200,
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, id):
        try:
            category = Category.objects.get(id=id, is_deleted=False)
        except Category.DoesNotExist:
            return Response(
                {"status": 404, "detail": "Kategori bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data_in = request.data

        is_del = data_in.get("is_deleted")
        if is_del is True or (isinstance(is_del, str) and is_del.lower() == "true"):
            category.is_deleted = True
            category.name = f"dlt_{category.name}"
            category.slug = f"dlt__{category.id}__{category.slug}"
            category.save(update_fields=["is_deleted", "name", "slug"])

            return Response(
                {"status": 200, "detail": "Kategori silindi."},
                status=status.HTTP_200_OK,
            )

        if "name" in data_in:
            name = (data_in.get("name") or "").strip()
            if name:
                category.name = name

        if "description" in data_in:
            category.description = data_in.get("description") or ""

        if "slug" in data_in:
            slug = (data_in.get("slug") or "").strip()
            if slug:
                if (
                    Category.objects.filter(slug=slug, is_deleted=False)
                    .exclude(id=category.id)
                    .exists()
                ):
                    return Response(
                        {"status": 400, "detail": "slug zaten kullanımda."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                category.slug = slug

        category.save()

        serializer = CategoryListSerializer(category)

        return Response(
            {
                "status": 200,
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 8 * 1024 * 1024
import logging
logger = logging.getLogger(__name__)
class CloudinaryUploadProductAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        folder = (request.data.get("folder") or "").strip() or None
        single = request.FILES.get("file")
        multiple = request.FILES.getlist("files")

        files = []
        if single:
            files = [single]
        elif multiple:
            files = multiple

        if not files:
            return Response(
                {"status": 400, "message": "Dosya bulunamadı."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_fligran_id = getattr(settings, "FLIGRAN_PUBLIC_ID", None)
        fligran_id = raw_fligran_id.split(".")[0] if raw_fligran_id else None

        out = []
        for f in files:
            ct = getattr(f, "content_type", None)

            if ct not in ALLOWED_MIME:
                continue

            if getattr(f, "size", 0) > MAX_BYTES:
                return Response(
                    {
                        "status": 400,
                        "message": f"Dosya çok büyük: {MAX_BYTES} byte sınırı var.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                upload_params = {
                    "folder": folder,
                    "resource_type": "image",
                    "overwrite": False,
                    "unique_filename": True,
                }

                if fligran_id:
                    upload_params["transformation"] = [
                        {"width": "1.0", "height": "1.0", "flags": "relative"},
                        {"overlay": fligran_id, "flags": "tiled"},
                    ]

                res = cloudinary.uploader.upload(f, **upload_params)

                out.append(
                    {
                        "url": res.get("secure_url") or res.get("url"),
                        "public_id": res.get("public_id"),
                        "width": res.get("width"),
                        "height": res.get("height"),
                        "bytes": res.get("bytes"),
                        "format": res.get("format"),
                        "original_filename": res.get("original_filename"),
                    }
                )

            except Exception as e:
                print(f"Cloudinary API Error: {str(e)}")
                return Response(
                    {"status": 500, "detail": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response({"status": 200, "results": out}, status=status.HTTP_200_OK)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 8 * 1024 * 1024  # 8MB (istersen değiştir)

class CloudinaryUploadCategoryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Accepts:
          - single:  file=<file>
          - multiple: files=<file1>&files=<file2>...
        Optional:
          - folder: "products/1" etc.
        Returns:
          - results: [{url, public_id, width, height, bytes, format, original_filename}]
        """

        folder = (request.data.get("folder") or "").strip() or None

        single = request.FILES.get("file")
        multiple = request.FILES.getlist("files")

        files = []
        if single:
            files = [single]
        elif multiple:
            files = multiple

        if not files:
            return Response(
                {"status": 400, "message": "Dosya bulunamadı."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        out = []
        for f in files:
            ct = getattr(f, "content_type", None)
            if ct not in ALLOWED_MIME:
                return Response(
                    {"status": 400, "message": f"Geçersiz dosya tipi: {ct}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if getattr(f, "size", 0) > MAX_BYTES:
                return Response(
                    {"status": 400, "message": f"Dosya çok büyük: {f.size} bytes. Maksimum: {MAX_BYTES}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                res = cloudinary.uploader.upload(
                    f,
                    folder=folder,
                    resource_type="image",
                    overwrite=False,
                    unique_filename=True,
                )
            except Exception as e:
                return Response(
                    {"status": 500, "detail": f"Cloudinary upload failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            out.append(
                {
                    "url": res.get("secure_url") or res.get("url"),
                    "public_id": res.get("public_id"),
                    "width": res.get("width"),
                    "height": res.get("height"),
                    "bytes": res.get("bytes"),
                    "format": res.get("format"),
                    "original_filename": res.get("original_filename"),
                }
            )

        return Response({"status": 200, "results": out}, status=status.HTTP_200_OK)


class CatalogUploadPDF(APIView):
    permission_classes = [IsAuthenticated] 
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        name = request.data.get("name")
        image_url = request.data.get("url")
        public_id = request.data.get("public_id")
        pdf_file = request.FILES.get("pdf")

        if not pdf_file:
            return Response({
                "status": 400, 
                "message": "Katalog PDF dosyası zorunludur."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_catalog = CatalogModel.objects.create(
                name=name,
                url=image_url,
                public_id=public_id,
                pdf_file=pdf_file
            )

            return Response({
                "status": 200,
                "message": "Katalog başarıyla kaydedildi.",
                "results": {
                    "id": new_catalog.id,
                    "name": new_catalog.name,
                    "pdf_url": request.build_absolute_uri(new_catalog.pdf_file.url),
                    "cover_image_url": new_catalog.url
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                "status": 500, 
                "message": f"Kayıt sırasında bir hata oluştu: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            

class CatalogListAPIView(ListAPIView):
    pagination_class = Pagination10
    serializer_class = CatalogSerializer
    
    def get_queryset(self):
        return CatalogModel.objects.filter(is_deleted=False).order_by("-created_at", "-id")

    def get(self, request, *args, **kwargs):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        
        serializer = self.get_serializer(page, many=True, context={'request': request})
        
        paginated_data = self.get_paginated_response(serializer.data).data

        return Response(
            {
                "status": 200,
                **paginated_data,
            },
            status=200,
        )
        

class CatalogDetailAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, id, *args, **kwargs):
        try:
            catalog = CatalogModel.objects.get(id=id, is_deleted=False)
        except CatalogModel.DoesNotExist:
            return Response(
                {"status": 404, "message": "Katalog bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CatalogSerializer(catalog, context={"request": request})
        return Response(
            {"status": 200, "data": serializer.data},
            status=status.HTTP_200_OK,
        )
    
    def patch(self, request, id, *args, **kwargs):
        try:
            catalog = CatalogModel.objects.get(id=id, is_deleted=False)
        except CatalogModel.DoesNotExist:
            return Response(
                {"status": 404, "message": "Katalog bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_deleted_val = request.data.get("is_deleted")
        if str(is_deleted_val).lower() == "true":
            if catalog.pdf_file:
                catalog.pdf_file.delete(save=False)
            
            catalog.is_deleted = True
            catalog.pdf_file = None
            catalog.url = None
            catalog.public_id = None
            catalog.save()
            
            return Response(
                {"status": 200, "message": "Katalog silindi ve dosyalar temizlendi."},
                status=status.HTTP_200_OK
            )

        name = request.data.get("name")
        image_url = request.data.get("url")
        public_id = request.data.get("public_id")
        new_pdf = request.FILES.get("pdf")

        if name:
            catalog.name = name
        if image_url:
            catalog.url = image_url
        if public_id:
            catalog.public_id = public_id
        
        if new_pdf:
            if catalog.pdf_file:
                catalog.pdf_file.delete(save=False)
            catalog.pdf_file = new_pdf

        catalog.save()

        serializer = CatalogSerializer(catalog, context={"request": request})
        return Response(
            {
                "status": 200, 
                "message": "Katalog başarıyla güncellendi.", 
                "data": serializer.data
            },
            status=status.HTTP_200_OK,
        )
    
class ProductCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        name = (request.data.get("name") or "").strip()
        description = (request.data.get("description") or "").strip()
        product_type = (request.data.get("product_type") or "").strip()
        tags = request.data.get("tags")
        category_id = request.data.get("category_id")
        images = request.data.get("images", [])
        stock = request.data.get("stock", 0)
        stock_code = (request.data.get("stock_code") or "").strip()

        if not name:
            return Response(
                {"status": 400, "message": "Ürün adı zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not product_type:
            return Response(
                {"status": 400, "message": "Ürün tipi zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        category = None
        if category_id not in (None, ""):
            try:
                category = Category.objects.get(id=category_id, is_deleted=False)
            except Category.DoesNotExist:
                return Response(
                    {"status": 400, "message": "Kategori bulunamadı."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
                
        if not isinstance(stock, int):
            return Response(
                {"status": 400, "message": "Stok sayısı integer olmalıdır."},
                status=status.HTTP_400_BAD_REQUEST,
            )
            
            

        slug = slugify(name)
        if not slug:
            slug = "product"
        base_slug = slug
        counter = 1
        while Products.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        tags_value = tags
        if tags_value in ("", None):
            tags_value = []
        if not isinstance(tags_value, list):
            return Response(
                {"status": 400, "message": "tags list olmalıdır."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product = Products.objects.create(
            name=name,
            description=description,
            product_type=product_type,
            slug=slug,
            tags=tags_value,
            category=category,
            stock=stock,
            stock_code=stock_code or None,
        )

        if images in (None, ""):
            images = []
        if not isinstance(images, list):
            return Response(
                {"status": 400, "message": "images list olmalıdır."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_images = []
        for idx, img in enumerate(images):
            if not isinstance(img, dict):
                return Response(
                    {"status": 400, "message": "images elemanları object olmalıdır."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            image_url = (img.get("image_url") or "").strip()
            alt_text = (img.get("alt_text") or "").strip()
            public_id = (img.get("public_id") or "").strip()

            if not image_url:
                return Response(
                    {"status": 400, "message": "image_url zorunludur."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pi = ProductImage.objects.create(
                product=product,
                image_url=image_url,
                alt_text=alt_text or None,
                public_id=public_id or None,
                is_primary=True if idx == 0 else False,
            )
            created_images.append(
                {
                    "id": pi.id,
                    "image_url": pi.image_url,
                    "alt_text": pi.alt_text,
                    "public_id": pi.public_id,
                    "is_primary": pi.is_primary,
                }
            )

        return Response(
            {
                "status": 201,
                "data": {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "product_type": product.product_type,
                    "slug": product.slug,
                    "tags": product.tags,
                    "category": product.category_id,
                    "images": created_images,
                    "created_at": product.created_at,
                },
            },
            status=status.HTTP_201_CREATED,
        )
    




class ProductCreateForProjectAPIView(APIView):

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        name = (request.data.get("name") or "").strip()
        description = (request.data.get("description") or "").strip()
        images = request.data.get("images", [])

        if not name:
            return Response(
                {"status": 400, "message": "Ürün adı zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    
            

        slug = slugify(name)
        if not slug:
            slug = "product"
        base_slug = slug
        counter = 1
        while Products.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1


        product = Products.objects.create(
            name=name,
            description=description,
            product_type=None,
            slug=slug,
            for_project=True,
        )

        if images in (None, ""):
            images = []
        if not isinstance(images, list):
            return Response(
                {"status": 400, "message": "images list olmalıdır."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_images = []
        for idx, img in enumerate(images):
            if not isinstance(img, dict):
                return Response(
                    {"status": 400, "message": "images elemanları object olmalıdır."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            image_url = (img.get("image_url") or "").strip()
            alt_text = (img.get("alt_text") or "").strip()
            public_id = (img.get("public_id") or "").strip()

            if not image_url:
                return Response(
                    {"status": 400, "message": "image_url zorunludur."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pi = ProductImage.objects.create(
                product=product,
                image_url=image_url,
                alt_text=alt_text or None,
                public_id=public_id or None,
                is_primary=True if idx == 0 else False,
            )
            created_images.append(
                {
                    "id": pi.id,
                    "image_url": pi.image_url,
                    "alt_text": pi.alt_text,
                    "public_id": pi.public_id,
                    "is_primary": pi.is_primary,
                }
            )

        return Response(
            {
                "status": 201,
                "data": {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "product_type": product.product_type,
                    "slug": product.slug,
                    "images": created_images,
                    "created_at": product.created_at,
                },
            },
            status=status.HTTP_201_CREATED,
        )
    


class ProductListAPIView(ListAPIView):
    serializer_class = ProductListSerializer
    pagination_class = Pagination10

    def get_queryset(self):
        image_qs = (
            ProductImage.objects.filter(is_deleted=False)
            .order_by("-is_primary", "id")
        )

        qs = (
            Products.objects.filter(is_deleted=False, for_project=False)
            .select_related("category")
            .prefetch_related(Prefetch("images", queryset=image_qs))
        )

        name = (self.request.query_params.get("name") or "").strip()
        if name:
            qs = qs.filter(name__icontains=name)

        product_type = (self.request.query_params.get("product_type") or "").strip()
        if product_type:
            qs = qs.filter(product_type__icontains=product_type)

        category_name = unquote_plus(
            self.request.query_params.get("category_name")
            or self.request.query_params.get("category")
            or ""
        ).strip()

        if category_name:
            normalized = category_name.lower().replace(",", "").replace(" ", "")

            qs = qs.annotate(
                normalized_category=Replace(
                    Replace(
                        Lower("category__name"),
                        Value(","), Value("")
                    ),
                    Value(" "), Value("")
                )
            ).filter(
                normalized_category__icontains=normalized
            )

        order_by = (self.request.query_params.get("order_by") or "desc").lower()
        if order_by == "asc":
            qs = qs.order_by("created_at", "id")
        else:
            qs = qs.order_by("-created_at", "-id")

        return qs
    


class ProjectListAPIView(ListAPIView):
    serializer_class = ProjectListSerializer
    pagination_class = Pagination10

    def get_queryset(self):
        image_qs = (
            ProductImage.objects.filter(is_deleted=False)
            .order_by("-is_primary", "id")
        )

        qs = (
            Products.objects.filter(is_deleted=False, for_project=True)
            .select_related("category")
            .prefetch_related(Prefetch("images", queryset=image_qs))
        )

        name = (self.request.query_params.get("name") or "").strip()
        if name:
            qs = qs.filter(name__icontains=name)

        product_type = (self.request.query_params.get("product_type") or "").strip()
        if product_type:
            qs = qs.filter(product_type__icontains=product_type)

        category_name = (self.request.query_params.get("category") or "").strip()
        if category_name:
            qs = qs.filter(
                category__is_deleted=False,
                category__name__icontains=category_name,
            )

        order_by = (self.request.query_params.get("order_by") or "desc").lower()
        if order_by == "asc":
            qs = qs.order_by("created_at", "id")
        else:
            qs = qs.order_by("-created_at", "-id")

        return qs
    
# class ProjectDetailAPIView(APIView):
#     def get(self, request, id, *args, **kwargs):
#         image_qs = (
#             ProductImage.objects.filter(is_deleted=False)
#             .order_by("-id")
#         )

#         try:
#             product = (
#                 Products.objects.select_related("category")
#                 .prefetch_related(Prefetch("images", queryset=image_qs))
#                 .get(id=id, is_deleted=False, for_project=True)
#             )
#         except Products.DoesNotExist:
#             return Response(
#                 {"status": 404, "message": "Proje bulunamadı."},
#                 status=status.HTTP_404_NOT_FOUND,
#             )

#         serializer = ProjectListSerializer(product, context={"request": request})
#         return Response(
#             {"status": 200, "data": serializer.data},
#             status=status.HTTP_200_OK,
#         )
        
#     @transaction.atomic
#     def patch(self, request, id, *args, **kwargs):
#         name = (request.data.get("name") or "").strip()
#         description = (request.data.get("description") or "").strip()

#         try:
#             product = Products.objects.get(id=id, is_deleted=False, for_project=True)
#         except Products.DoesNotExist:
#             return Response(
#                 {"status": 404, "message": "Proje bulunamadı."},
#                 status=status.HTTP_404_NOT_FOUND,
#             )

#         if name:
#             product.name = name

#         if description:
#             product.description = description

#         product.save()

#         if "images" in request.data:
#             images = request.data.get("images")

#             if images in (None, ""):
#                 images = []

#             if not isinstance(images, list):
#                 return Response(
#                     {"status": 400, "message": "Resimler doğru formatta gönderilmelidir."},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )

#             ProductImage.objects.filter(product=product, is_deleted=False).update(is_deleted=True)

#             created_images = []
#             for idx, img in enumerate(images):
#                 if not isinstance(img, dict):
#                     return Response(
#                         {"status": 400, "message": "Resim doğru formatta gönderilmelidir."},
#                         status=status.HTTP_400_BAD_REQUEST,
#                     )

#                 image_url = (img.get("image_url") or "").strip()
#                 public_id = (img.get("public_id") or "").strip()

#                 if not image_url:
#                     return Response(
#                         {"status": 400, "message": "Resim URL'si zorunludur."},
#                         status=status.HTTP_400_BAD_REQUEST,
#                     )

#                 pi = ProductImage.objects.create(
#                     product=product,
#                     image_url=image_url,
#                     public_id=public_id or None,
#                     is_primary=True if idx == 0 else False,
#                     is_deleted=False,
#                 )

#                 created_images.append(
#                     {
#                         "id": pi.id,
#                         "image_url": pi.image_url,
#                         "alt_text": pi.alt_text,
#                         "public_id": pi.public_id,
#                         "is_primary": pi.is_primary,
#                     }
#                 )

#             return Response(
#                 {
#                     "status": 200,
#                     "data": {
#                         "id": product.id,
#                         "name": product.name,
#                         "description": product.description,
#                         "product_type": product.product_type,
#                         "slug": product.slug,
#                         "images": created_images,
#                         "created_at": product.created_at,
#                     },
#                 },
#                 status=status.HTTP_200_OK,
#             )

#         serializer = ProjectListSerializer(product, context={"request": request})
#         return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)
        



class ProductDetailCustomerAPIView(APIView):

    def get(self, request, id, *args, **kwargs):
        image_qs = (
            ProductImage.objects.filter(is_deleted=False)
            .order_by("-is_primary", "id")  # primary önce
        )

        try:
            product = (
                Products.objects.select_related("category")
                .prefetch_related(Prefetch("images", queryset=image_qs))
                .get(id=id, is_deleted=False)
            )
        except Products.DoesNotExist:
            return Response(
                {"status": 404, "message": "Ürün bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProductListSerializer(product, context={"request": request})
        return Response(
            {"status": 200, "data": serializer.data},
            status=status.HTTP_200_OK,
        )


class ProductDetailAPIView(APIView):

    def get(self, request, id, *args, **kwargs):
        image_qs = (
            ProductImage.objects.filter(is_deleted=False)
            .order_by("-is_primary", "id")  # primary önce
        )

        try:
            product = (
                Products.objects.select_related("category")
                .prefetch_related(Prefetch("images", queryset=image_qs))
                .get(id=id, is_deleted=False)
            )
        except Products.DoesNotExist:
            return Response(
                {"status": 404, "message": "Ürün bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProductListSerializer(product, context={"request": request})
        return Response(
            {"status": 200, "data": serializer.data},
            status=status.HTTP_200_OK,
        )
    
    @transaction.atomic
    def patch(self, request, id, *args, **kwargs):
        try:
            product = Products.objects.get(id=id, is_deleted=False)
        except Products.DoesNotExist:
            return Response(
                {"status": 404, "message": "Ürün bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data_in = request.data

        is_del = data_in.get("is_deleted")
        if is_del is True or (isinstance(is_del, str) and is_del.lower() == "true"):
            product.is_deleted = True
            product.name = f"dlt_{product.name}"
            product.slug = f"dlt__{product.id}__{product.slug}"
            product.save(update_fields=["is_deleted", "name", "slug"])

            ProductImage.objects.filter(product=product).update(
                is_deleted=True, is_primary=False
            )

            return Response(
                {"status": 200, "message": "Ürün silindi."},
                status=status.HTTP_200_OK,
            )

        if "name" in data_in:
            name = (data_in.get("name") or "").strip()
            if name:
                product.name = name

                new_slug = slugify(name) or "product"
                base_slug = new_slug
                counter = 1
                slug_candidate = new_slug
                while (
                    Products.objects.filter(slug=slug_candidate)
                    .exclude(id=product.id)
                    .exists()
                ):
                    slug_candidate = f"{base_slug}-{counter}"
                    counter += 1
                product.slug = slug_candidate

        if "description" in data_in:
            product.description = (data_in.get("description") or "").strip()

        if "product_type" in data_in:
            product_type = (data_in.get("product_type") or "").strip()
            product.product_type = product_type or None

        if "tags" in data_in:
            tags = data_in.get("tags")
            if tags in ("", None):
                tags = []
            if not isinstance(tags, list):
                return Response(
                    {"status": 400, "message": "tags list olmalıdır."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            product.tags = tags

        if "category_id" in data_in:
            category_id = data_in.get("category_id")
            if category_id in ("", None):
                product.category = None
            else:
                try:
                    category = Category.objects.get(id=category_id, is_deleted=False)
                except Category.DoesNotExist:
                    return Response(
                        {"status": 400, "message": "Kategori bulunamadı."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                product.category = category
                
        if "stock" in data_in:
            stock = data_in.get("stock")
            if not isinstance(stock, int):
                return Response(
                    {"status": 400, "message": "Stok sayısı integer olmalıdır."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            product.stock = stock
            
        if "stock_code" in data_in:
            stock_code = (data_in.get("stock_code") or "").strip()
            product.stock_code = stock_code or None

        product.save()

        if "images" in data_in:
            images = data_in.get("images", [])
            if images in (None, ""):
                images = []
            if not isinstance(images, list):
                return Response(
                    {"status": 400, "message": "images list olmalıdır."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ProductImage.objects.filter(product=product, is_deleted=False).update(
                is_deleted=True, is_primary=False
            )

            for idx, img in enumerate(images):
                if not isinstance(img, dict):
                    return Response(
                        {
                            "status": 400,
                            "message": "images elemanları object olmalıdır.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                image_url = (img.get("image_url") or "").strip()
                alt_text = (img.get("alt_text") or "").strip()
                public_id = (img.get("public_id") or "").strip()

                if not image_url:
                    return Response(
                        {"status": 400, "message": "image_url zorunludur."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                ProductImage.objects.create(
                    product=product,
                    image_url=image_url,
                    alt_text=alt_text or None,
                    public_id=public_id or None,
                    is_primary=True if idx == 0 else False,
                )

        image_qs = (
            ProductImage.objects.filter(is_deleted=False)
            .order_by("-is_primary", "id")
        )

        product = (
            Products.objects.select_related("category")
            .prefetch_related(Prefetch("images", queryset=image_qs))
            .get(id=product.id)
        )

        serializer = ProductListSerializer(product, context={"request": request})
        return Response(
            {"status": 200, "data": serializer.data},
            status=status.HTTP_200_OK,
        )


class ProjectDetailAPIView(APIView):

    def _build_product_data(self, product):
        images_out = []
        for img in getattr(product, "images", []).all():
            if img.is_deleted:
                continue
            if hasattr(img, "for_project") and not img.for_project:
                continue

            images_out.append(
                {
                    "id": img.id,
                    "image_url": img.image_url,
                    "alt_text": img.alt_text,
                    "public_id": img.public_id,
                    "is_primary": img.is_primary,
                    "created_at": img.created_at,
                }
            )

        return {
            "id": product.id,
            "name": product.name,
            "images": images_out,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
            "description": product.description,
        }

    def get(self, request, id, *args, **kwargs):
        image_qs = ProductImage.objects.filter(is_deleted=False).order_by("-is_primary", "id")
        if hasattr(ProductImage, "for_project"):
            image_qs = image_qs.filter(for_project=True)

        try:
            product = (
                Products.objects.select_related("category")
                .prefetch_related(Prefetch("images", queryset=image_qs))
                .get(id=id, is_deleted=False, for_project=True)
            )
        except Products.DoesNotExist:
            return Response(
                {"status": 404, "message": "Proje ürünü bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"status": 200, "data": self._build_product_data(product)},
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def patch(self, request, id, *args, **kwargs):
        try:
            product = Products.objects.get(id=id, is_deleted=False, for_project=True)
        except Products.DoesNotExist:
            return Response(
                {"status": 404, "message": "Proje ürünü bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data_in = request.data

        is_del = data_in.get("is_deleted")
        if is_del is True or (isinstance(is_del, str) and str(is_del).lower() == "true"):
            product.is_deleted = True
            product.name = f"dlt_{product.name}"
            product.slug = f"dlt__{product.id}__{product.slug}"
            product.save(update_fields=["is_deleted", "name", "slug"])

            ProductImage.objects.filter(product=product, is_deleted=False).update(
                is_deleted=True, is_primary=False
            )

            return Response(
                {"status": 200, "message": "Proje ürünü silindi."},
                status=status.HTTP_200_OK,
            )

        if "name" in data_in:
            name = (data_in.get("name") or "").strip()
            if not name:
                return Response(
                    {"status": 400, "message": "name boş olamaz."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            product.name = name

            new_slug = slugify(name) or "product"
            base_slug = new_slug
            counter = 1
            slug_candidate = new_slug
            while (
                Products.objects.filter(slug=slug_candidate)
                .exclude(id=product.id)
                .exists()
            ):
                slug_candidate = f"{base_slug}-{counter}"
                counter += 1
            product.slug = slug_candidate
            
        if "description" in data_in:
            product.description = (data_in.get("description") or "").strip()
            product.description = product.description or ""


        product.save()

        if "images" in data_in:
            images = data_in.get("images", [])
            if images in (None, ""):
                images = []
            if not isinstance(images, list):
                return Response(
                    {"status": 400, "message": "images list olmalıdır."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Eski aktif resimleri soft delete
            ProductImage.objects.filter(product=product, is_deleted=False).update(
                is_deleted=True, is_primary=False
            )

            for idx, img in enumerate(images):
                if not isinstance(img, dict):
                    return Response(
                        {"status": 400, "message": "images elemanları object olmalıdır."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                image_url = (img.get("image_url") or "").strip()
                alt_text = (img.get("alt_text") or "").strip()
                public_id = (img.get("public_id") or "").strip()

                if not image_url:
                    return Response(
                        {"status": 400, "message": "image_url zorunludur."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                create_kwargs = dict(
                    product=product,
                    image_url=image_url,
                    alt_text=alt_text or None,
                    public_id=public_id or None,
                    is_primary=True if idx == 0 else False,
                )
                if hasattr(ProductImage, "for_project"):
                    create_kwargs["for_project"] = True

                ProductImage.objects.create(**create_kwargs)

        image_qs = ProductImage.objects.filter(is_deleted=False).order_by("-is_primary", "id")
        if hasattr(ProductImage, "for_project"):
            image_qs = image_qs.filter(for_project=True)

        product = (
            Products.objects.select_related("category")
            .prefetch_related(Prefetch("images", queryset=image_qs))
            .get(id=product.id, is_deleted=False, for_project=True)
        )

        return Response(
            {"status": 200, "data": self._build_product_data(product)},
            status=status.HTTP_200_OK,
        )



class CreateReferenceCategoryAPIView(APIView):

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        name = (request.data.get("name") or "").strip()

        if not name:
            return Response(
                {"status": 400, "message": "Kategori adı zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if ReferenceCategory.objects.filter(
            name__iexact=name, is_deleted=False
        ).exists():
            return Response(
                {"status": 400, "message": "Bu isimde bir kategori zaten mevcut."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        category = ReferenceCategory.objects.create(
            name=name
        )

        return Response(
            {
                "status": 201,
                "data": {
                    "id": category.id,
                    "name": category.name,
                    "created_at": category.created_at,
                },
            },
            status=status.HTTP_201_CREATED,
        )

class ReferenceCategoryListAPIView(APIView):
    pagination_class = Pagination10

    def get(self, request, *args, **kwargs):
        qs = (
            ReferenceCategory.objects.filter(is_deleted=False)
            .order_by("-created_at")
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)

        results = [
            {
                "id": cat.id,
                "name": cat.name,
                "created_at": cat.created_at,
            }
            for cat in page
        ]

        paginated = paginator.get_paginated_response(results)
        paginated.data["status"] = 200
        return paginated

class CreateReferenceAPIView(APIView):

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        name = (request.data.get("name") or "").strip()
        ref_category_id = request.data.get("ref_category")
        images = request.data.get("images", [])

        if not name:
            return Response(
                {"status": 400, "message": "name zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if ref_category_id in (None, ""):
            return Response(
                {"status": 400, "message": "ref_category zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ref_category = ReferenceCategory.objects.get(
                id=ref_category_id, is_deleted=False
            )
        except ReferenceCategory.DoesNotExist:
            return Response(
                {"status": 400, "message": "Kategori bulunamadı."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if images in (None, ""):
            images = []
        if not isinstance(images, list):
            return Response(
                {"status": 400, "message": "Resimler doğru formatta olmalıdır."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reference = ReferenceModel.objects.create(
            name=name,
            ref_category=ref_category,
        )

        created_images = []
        for idx, img in enumerate(images):
            if not isinstance(img, dict):
                return Response(
                    {
                        "status": 400,
                        "message": "Resim elemanları doğru formatta yüklenmelidir.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            image_url = (img.get("image_url") or "").strip()
            alt_text = (img.get("alt_text") or "").strip()
            public_id = (img.get("public_id") or "").strip()

            if not image_url:
                return Response(
                    {"status": 400, "message": "Resim url'si zorunludur."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ri = ReferenceImage.objects.create(
                reference=reference,
                image_url=image_url,
                alt_text=alt_text or None,
                public_id=public_id or None,
                is_primary=True if idx == 0 else False,
            )

            created_images.append(
                {
                    "id": ri.id,
                    "image_url": ri.image_url,
                    "alt_text": ri.alt_text,
                    "public_id": ri.public_id,
                    "is_primary": ri.is_primary,
                    "created_at": ri.created_at,
                }
            )

        return Response(
            {
                "status": 201,
                "data": {
                    "id": reference.id,
                    "name": reference.name,
                    "ref_category": reference.ref_category_id,
                    "images": created_images,
                    "created_at": reference.created_at,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class ReferenceListAPIView(APIView):
    pagination_class = Pagination10

    def get(self, request, *args, **kwargs):
        name_q = (request.query_params.get("name") or "").strip()
        category_q = (request.query_params.get("category") or "").strip()
        order_q = (request.query_params.get("order") or "desc").lower()

        if order_q == "asc":
            order_by_field = "id"
        else:
            order_by_field = "-id"

        qs = (
            ReferenceModel.objects.filter(is_deleted=False)
            .select_related("ref_category")
            .prefetch_related("ref_images")
            .order_by(order_by_field)
        )

        if name_q:
            qs = qs.filter(name__icontains=name_q)

        if category_q:
            qs = qs.filter(ref_category__is_deleted=False, ref_category__name__icontains=category_q)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)

        results = []
        for ref in page:
            images = [
                {
                    "id": img.id,
                    "image_url": img.image_url,
                    "alt_text": img.alt_text,
                    "public_id": img.public_id,
                    "is_primary": img.is_primary,
                    "created_at": img.created_at,
                }
                for img in ref.ref_images.all()
                if not img.is_deleted
            ]

            results.append(
                {
                    "id": ref.id,
                    "name": ref.name,
                    "ref_category": ref.ref_category_id,
                    "ref_category_name": ref.ref_category.name if ref.ref_category else None,
                    "images": images,
                    "created_at": ref.created_at,
                }
            )

        paginated = paginator.get_paginated_response(results)
        paginated.data["status"] = 200
        return paginated
    


class ReferenceUpdateAPIView(APIView):

    @transaction.atomic
    def patch(self, request, id, *args, **kwargs):
        # 1) Reference'ı bul
        try:
            reference = (
                ReferenceModel.objects
                .select_related("ref_category")
                .prefetch_related("ref_images")
                .get(id=id, is_deleted=False)
            )
        except ReferenceModel.DoesNotExist:
            return Response(
                {"status": 404, "message": "Reference bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data_in = request.data

        # 2) Soft delete (reference + images)
        is_del = data_in.get("is_deleted")
        if is_del is True or (isinstance(is_del, str) and is_del.lower() == "true"):
            reference.is_deleted = True
            reference.save(update_fields=["is_deleted"])

            ReferenceImage.objects.filter(reference=reference, is_deleted=False).update(
                is_deleted=True, is_primary=False
            )

            return Response(
                {"status": 200, "message": "Reference silindi."},
                status=status.HTTP_200_OK,
            )

        # 3) name güncelle
        if "name" in data_in:
            name = (data_in.get("name") or "").strip()
            if not name:
                return Response(
                    {"status": 400, "message": "name boş olamaz."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            reference.name = name

        # 4) ref_category güncelle (id ile)
        if "ref_category" in data_in:
            ref_category_id = data_in.get("ref_category")
            if ref_category_id in (None, ""):
                reference.ref_category = None
            else:
                try:
                    ref_cat = ReferenceCategory.objects.get(
                        id=ref_category_id, is_deleted=False
                    )
                except ReferenceCategory.DoesNotExist:
                    return Response(
                        {"status": 400, "message": "Kategori bulunamadı."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                reference.ref_category = ref_cat

        reference.save()

        # 5) images gönderildiyse: eskileri is_deleted=True yap, yenileri oluştur
        created_images = None
        if "images" in data_in:
            images = data_in.get("images", [])
            if images in (None, ""):
                images = []
            if not isinstance(images, list):
                return Response(
                    {"status": 400, "message": "images list olmalıdır."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # eski resimleri sil (soft delete)
            ReferenceImage.objects.filter(reference=reference, is_deleted=False).update(
                is_deleted=True, is_primary=False
            )

            created_images = []
            for idx, img in enumerate(images):
                if not isinstance(img, dict):
                    return Response(
                        {"status": 400, "message": "images elemanları object olmalıdır."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                image_url = (img.get("image_url") or "").strip()
                alt_text = (img.get("alt_text") or "").strip()
                public_id = (img.get("public_id") or "").strip()

                if not image_url:
                    return Response(
                        {"status": 400, "message": "image_url zorunludur."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                ri = ReferenceImage.objects.create(
                    reference=reference,
                    image_url=image_url,
                    alt_text=alt_text or None,
                    public_id=public_id or None,
                    is_primary=True if idx == 0 else False,
                )

                created_images.append(
                    {
                        "id": ri.id,
                        "image_url": ri.image_url,
                        "alt_text": ri.alt_text,
                        "public_id": ri.public_id,
                        "is_primary": ri.is_primary,
                        "created_at": ri.created_at,
                    }
                )

        # 6) response: images güncellendiyse created_images dön, değilse mevcut aktifleri dön
        if created_images is None:
            active_images = ReferenceImage.objects.filter(
                reference=reference, is_deleted=False
            ).order_by("-is_primary", "-created_at", "-id")

            images_out = [
                {
                    "id": img.id,
                    "image_url": img.image_url,
                    "alt_text": img.alt_text,
                    "public_id": img.public_id,
                    "is_primary": img.is_primary,
                    "created_at": img.created_at,
                }
                for img in active_images
            ]
        else:
            images_out = created_images

        return Response(
            {
                "status": 200,
                "data": {
                    "id": reference.id,
                    "name": reference.name,
                    "ref_category": reference.ref_category_id,
                    "ref_category_name": reference.ref_category.name if reference.ref_category else None,
                    "images": images_out,
                    "created_at": reference.created_at,
                },
            },
            status=status.HTTP_200_OK,
        )
    


class ReferenceDetail(APIView):

    def get(self, request, id, *args, **kwargs):
        try:
            reference = (
                ReferenceModel.objects
                .select_related("ref_category")
                .prefetch_related("ref_images")
                .get(id=id, is_deleted=False)
            )
        except ReferenceModel.DoesNotExist:
            return Response(
                {"status": 404, "message": "Reference bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        images_qs = (
            ReferenceImage.objects
            .filter(reference=reference, is_deleted=False)
            .order_by("-is_primary", "-created_at", "-id")
        )

        images_out = [
            {
                "id": img.id,
                "image_url": img.image_url,
                "alt_text": img.alt_text,
                "public_id": img.public_id,
                "is_primary": img.is_primary,
                "created_at": img.created_at,
            }
            for img in images_qs
        ]

        return Response(
            {
                "status": 200,
                "data": {
                    "id": reference.id,
                    "name": reference.name,
                    "ref_category": reference.ref_category_id,
                    "ref_category_name": reference.ref_category.name if reference.ref_category else None,
                    "images": images_out,
                    "created_at": reference.created_at,
                },
            },
            status=status.HTTP_200_OK,
        )
        

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
class LandingPagePostCreateAPIView(APIView):

    def post(self, request, *args, **kwargs):
        data = request.data

        section_key = data.get("section_key")
        title = data.get("title", "").strip()
        description = data.get("description", "")
        title_en = data.get("title_en", "").strip()
        description_en = data.get("description_en", "")
        image_url = data.get("image_url")
        public_id = data.get("public_id")
        title_font_family = data.get("title_font_family")
        font_family = data.get("font_family")
        

        if not section_key:
            return Response(
                {"detail": "Oluşturulacak alan seçimi zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if LandingPage.objects.filter(
            section_key=section_key,
            is_deleted=False
        ).exists():
            return Response(
                {"detail": "Bu alan için zaten kayıt mevcut."},
                status=status.HTTP_409_CONFLICT,
            )

        if title_font_family and title_font_family not in ALLOWED_FONTS:
            return Response(
                {"detail": "Geçersiz yazı tipi değeri."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if font_family and font_family not in ALLOWED_FONTS:
            return Response(
                {"detail": "Geçersiz yazı tipi değeri."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            section = LandingPage.objects.create(
                section_key=section_key,
                title=title,
                description=description,
                title_en=title_en,
                description_en=description_en,
                image_url=image_url,
                public_id=public_id,
                title_font_family=title_font_family,
                font_family=font_family,
            )
        except IntegrityError:
            return Response(
                {"detail": "Kayıt oluşturulamadı."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "id": section.id,
                "section_key": section.section_key,
                "title": section.title,
                "description": section.description,
                "title_en": section.title_en,
                "description_en": section.description_en,
                "image_url": section.image_url,
                "public_id": section.public_id,
                "title_font_family": section.title_font_family,
                "font_family": section.font_family,
            },
            status=status.HTTP_201_CREATED,
        )
        

class LandingPageListAPIView(APIView):
    pagination_class = Pagination10

    def get(self, request, *args, **kwargs):
        queryset = LandingPage.objects.filter(is_deleted=False).order_by("id")

        section_key = request.query_params.get("section_key")
        if section_key:
            queryset = queryset.filter(section_key=section_key)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        serializer = LandingPageListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
    


class LandingPageDetailAPIView(APIView):
    def get(self, request, id, *args, **kwargs):
        try:
            landing_page = LandingPage.objects.get(
                id=id,
                is_deleted=False
            )
        except LandingPage.DoesNotExist:
            return Response(
                {"detail": "Kayıt bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = LandingPageListSerializer(landing_page)

        return Response(
            {
                "data": serializer.data
            },
            status=status.HTTP_200_OK,
        )
    
    def patch(self, request, id, *args, **kwargs):
        try:
            landing_page = LandingPage.objects.get(id=id, is_deleted=False)
        except LandingPage.DoesNotExist:
            return Response(
                {"detail": "Kayıt bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data
        
        
        is_deleted = data.get("is_deleted")
        
        if is_deleted is True or (isinstance(is_deleted, str) and str(is_deleted).lower() == "true"):
            landing_page.is_deleted = True
            landing_page.save(update_fields=["is_deleted"])
            return Response(
                {"detail": "Kayıt silindi."},
                status=status.HTTP_200_OK,
            )
            
        title = data.get("title")
        description = data.get("description")
        title_en = data.get("title_en")
        description_en = data.get("description_en")
        image_url = data.get("image_url")
        public_id = data.get("public_id")
        title_font_family = data.get("title_font_family")
        font_family = data.get("font_family")
        section_key = data.get("section_key")

        if title is not None:
            landing_page.title = title.strip()

        if description is not None:
            landing_page.description = description
            
        if title_en is not None:
            landing_page.title_en = title_en.strip()

        if description_en is not None:
            landing_page.description_en = description_en

        if image_url is not None:
            landing_page.image_url = image_url

        if public_id is not None:
            landing_page.public_id = public_id
            
        if section_key is not None:
            landing_page.section_key = section_key

        if title_font_family is not None:
            if title_font_family and title_font_family not in ALLOWED_FONTS:
                return Response(
                    {"detail": "Geçersiz yazı tipi değeri."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            landing_page.title_font_family = title_font_family

        if font_family is not None:
            if font_family and font_family not in ALLOWED_FONTS:
                return Response(
                    {"detail": "Geçersiz yazı tipi değeri."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            landing_page.font_family = font_family

        landing_page.save()

        serializer = LandingPageListSerializer(landing_page)
        return Response(serializer.data)
    
    
    

class BannerImageCreate(APIView):
    """
    Body:
    {
      "images": [
        {"image_url": "...", "public_id": "...", "alt_text": "..."},
        {"image_url": "...", "public_id": "..."}
      ]
    }

    - Her image için BannerImageModel + Banner oluşturur
    - Sistemde hiç primary yoksa, bu batch'in ilk elemanı is_primary=True olur
    """

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        images = request.data.get("images")

        if not isinstance(images, list) or not images:
            return Response(
                {"detail": "images alanı dolu bir liste olmalıdır."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        primary_exists = BannerImageModel.objects.filter(is_deleted=False, is_primary=True).exists()

        created = []
        for idx, item in enumerate(images):
            if not isinstance(item, dict):
                return Response(
                    {"detail": f"images[{idx}] obje olmalıdır."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            image_url = (item.get("image_url") or "").strip()
            public_id = (item.get("public_id") or "").strip()
            alt_text = (item.get("alt_text") or "").strip() or None

            if not image_url or not public_id:
                return Response(
                    {"detail": f"images[{idx}] için image_url ve public_id zorunludur."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            is_primary = (not primary_exists) and (idx == 0)

            banner_image = BannerImageModel.objects.create(
                image_url=image_url,
                public_id=public_id,
                alt_text=alt_text,
                is_primary=is_primary,
            )

            banner = Banner.objects.create(banner=banner_image)

            created.append(
                {
                    "id": banner_image.id,
                    "banner_id": banner.id,
                    "image_url": banner_image.image_url,
                    "public_id": banner_image.public_id,
                    "alt_text": banner_image.alt_text,
                    "is_primary": banner_image.is_primary,
                    "created_at": banner_image.created_at,
                }
            )

        return Response(
            {
                "count": len(created),
                "results": created,
            },
            status=status.HTTP_201_CREATED,
        )
        

class BannerImageListAPIView(APIView):
    pagination_class = Pagination10

    def get(self, request, *args, **kwargs):
        qs = (
            BannerImageModel.objects
            .filter(is_deleted=False)
            .order_by("id")
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)

        serializer = BannerImageListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

class BannerImageDetailAPIView(APIView):
    def get(self, request, id, *args, **kwargs):
        try:
            banner_image = BannerImageModel.objects.get(
                id=id,
                is_deleted=False
            )
        except BannerImageModel.DoesNotExist:
            return Response(
                {"detail": "Kayıt bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = BannerImageListSerializer(banner_image)

        return Response(
            {
                "data": serializer.data
            },
            status=status.HTTP_200_OK,
        )
        
    @transaction.atomic
    def patch(self, request, id, *args, **kwargs):
        try:
            banner_image = BannerImageModel.objects.get(id=id, is_deleted=False)
        except BannerImageModel.DoesNotExist:
            return Response(
                {"detail": "Kayıt bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data
        is_deleted = data.get("is_deleted")

        if is_deleted is True or (isinstance(is_deleted, str) and str(is_deleted).lower() == "true"):
            banner_image.is_deleted = True
            banner_image.is_primary = False
            banner_image.save(update_fields=["is_deleted", "is_primary"])

            next_primary = (
                BannerImageModel.objects
                .filter(is_deleted=False, id__gt=banner_image.id)
                .order_by("id")
                .first()
            )

            if next_primary is None:
                next_primary = (
                    BannerImageModel.objects
                    .filter(is_deleted=False)
                    .order_by("id")
                    .first()
                )

            if next_primary:
                BannerImageModel.objects.filter(is_deleted=False, is_primary=True).update(is_primary=False)
                next_primary.is_primary = True
                next_primary.save(update_fields=["is_primary"])

                return Response(
                    {
                        "detail": "Kayıt silindi. Yeni primary atandı.",
                        "new_primary_id": next_primary.id,
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {"detail": "Kayıt silindi. Aktif kayıt kalmadığı için primary atanmadı."},
                status=status.HTTP_200_OK,
            )

        image_url = data.get("image_url")
        public_id = data.get("public_id")
        alt_text = data.get("alt_text")

        if image_url is not None:
            banner_image.image_url = image_url

        if public_id is not None:
            banner_image.public_id = public_id

        if alt_text is not None:
            banner_image.alt_text = alt_text

        banner_image.save()

        serializer = BannerImageListSerializer(banner_image)
        return Response(serializer.data, status=status.HTTP_200_OK)