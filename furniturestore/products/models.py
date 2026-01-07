from django.db import models

from users.models import Users


class Products(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)

    description = models.CharField(max_length=2048, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    
    stock = models.IntegerField(default=0)
    
    stock_code = models.CharField(max_length=100, null=True, blank=True)

    is_deleted = models.BooleanField(default=False)

    slug = models.SlugField(max_length=255, unique=True)

    tags = models.JSONField(default=list, blank=True, null=True)

    product_type = models.CharField(max_length=255, null=True, blank=True)

    for_project = models.BooleanField(default=False, null=True, blank=True)

    category = models.ForeignKey(
        "Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )


class ProductImage(models.Model):
    product = models.ForeignKey(
        Products,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image_url = models.URLField(max_length=2000, null=True, blank=True)

    alt_text = models.CharField(max_length=255, blank=True, null=True)

    is_primary = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    public_id = models.CharField(max_length=255, blank=True, null=True)

    is_deleted = models.BooleanField(default=False)



class Category(models.Model):
    name = models.CharField(max_length=255)

    description = models.CharField(max_length=2048)

    created_at = models.DateTimeField(auto_now_add=True)

    is_deleted = models.BooleanField(default=False)

    slug = models.SlugField(max_length=255, unique=True)

    image_url = models.URLField(max_length=2000, null=True, blank=True)

    public_id = models.CharField(max_length=255, blank=True, null=True)




class ReferenceCategory(models.Model):
    name = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    is_deleted = models.BooleanField(default=False)


class ReferenceModel(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)

    type = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    is_deleted = models.BooleanField(default=False)

    ref_category = models.ForeignKey(
        ReferenceCategory,
        on_delete=models.CASCADE,
        related_name="ref_category",
        null=True,
        blank=True
    )

    

class ReferenceImage(models.Model):
    reference = models.ForeignKey(
        ReferenceModel,
        on_delete=models.CASCADE,
        related_name="ref_images",
    )

    image_url = models.URLField(max_length=2000, null=True, blank=True)

    alt_text = models.CharField(max_length=255, blank=True, null=True)

    is_primary = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    public_id = models.CharField(max_length=255, blank=True, null=True)

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)




class CatalogModel(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    
    url = models.URLField(max_length=2000, null=True, blank=True)
    
    public_id = models.CharField(max_length=255, blank=True, null=True)
    
    pdf_file = models.FileField(upload_to='catalogs/pdfs/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    is_deleted = models.BooleanField(default=False)
    
    
class LandingPage(models.Model):
    section_key = models.CharField(max_length=255, blank=True, null=True)
    
    title = models.CharField(max_length=255, blank=True, null=True)
    
    description = models.CharField(max_length=2048, blank=True, null=True)
    
    title_en = models.CharField(max_length=255, blank=True, null=True)
    
    description_en = models.CharField(max_length=2048, blank=True, null=True)
    
    image_url = models.URLField(max_length=2000, null=True, blank=True)
    
    public_id = models.CharField(max_length=255, blank=True, null=True) 
    
    title_font_family = models.CharField(max_length=255, blank=True, null=True)
    
    font_family = models.CharField(max_length=255, blank=True, null=True)
    
    is_deleted = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    


class BannerImageModel(models.Model):
    image_url = models.URLField(max_length=2000, null=True, blank=True)

    alt_text = models.CharField(max_length=255, blank=True, null=True)

    is_primary = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    public_id = models.CharField(max_length=255, blank=True, null=True)

    is_deleted = models.BooleanField(default=False)

class Banner(models.Model):
    banner = models.ForeignKey(
        BannerImageModel,
        on_delete=models.CASCADE,
        related_name="banners",
    )