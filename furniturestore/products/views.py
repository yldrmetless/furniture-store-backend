
import cloudinary.uploader
from django.db import transaction
from django.utils.text import slugify
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from products.serializers import ProductListSerializer,ProjectListSerializer
from django.db.models import Prefetch
from django.db.models import Count, Q

from products.models import (
    Category,
    ProductImage,
    Products,
    ReferenceImage,
    ReferenceModel,
    ReferenceCategory
)
from products.pagination import Pagination10
from products.serializers import (
    CategoryListSerializer,
)
# Create your views here.

class CategoryCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

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
    permission_classes = [IsAuthenticated, IsAdminUser]

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
MAX_BYTES = 8 * 1024 * 1024  # 8MB (istersen değiştir)

class CloudinaryUploadAPIView(APIView):
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
                {"status": 400, "detail": "No file provided. Send 'file' or 'files'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        out = []
        for f in files:
            ct = getattr(f, "content_type", None)
            if ct not in ALLOWED_MIME:
                return Response(
                    {"status": 400, "detail": f"Invalid file type: {ct}. Allowed: jpg, png, webp."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if getattr(f, "size", 0) > MAX_BYTES:
                return Response(
                    {"status": 400, "detail": f"File too large: {f.size} bytes. Max: {MAX_BYTES}."},
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
    



class ProductCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        name = (request.data.get("name") or "").strip()
        description = (request.data.get("description") or "").strip()
        product_type = (request.data.get("product_type") or "").strip()
        tags = request.data.get("tags")
        category_id = request.data.get("category_id")
        images = request.data.get("images", [])

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
    permission_classes = [IsAuthenticated, IsAdminUser]

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
            for_project=True
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
    permission_classes = [IsAuthenticated, IsAdminUser]

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
    permission_classes = [IsAuthenticated, IsAdminUser]

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
    permission_classes = [IsAuthenticated, IsAdminUser]

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
    permission_classes = [IsAuthenticated, IsAdminUser]

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