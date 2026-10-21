from django.db import models


class Product(models.Model):
    """Local storefront snapshot of one item in Chortke."""

    chortke_code = models.CharField(max_length=100, unique=True)
    accounting_code = models.CharField(max_length=100, blank=True)
    barcode = models.CharField(max_length=128, blank=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    description_override = models.TextField(blank=True)
    unit = models.CharField(max_length=32, blank=True)
    stock = models.DecimalField(max_digits=16, decimal_places=3, default=None, null=True, blank=True)
    sale_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    image_url = models.CharField(max_length=1000, blank=True)
    custom_image = models.ImageField(upload_to="product-images/custom/", blank=True)
    image_source_url = models.URLField(max_length=1000, blank=True)
    image_size = models.PositiveIntegerField(default=0)
    description_sources = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_visible = models.BooleanField(default=True, db_index=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "chortke_code"]
        indexes = [models.Index(fields=["is_active", "name"], name="catalog_prod_active_name")]
        verbose_name = "کالا"
        verbose_name_plural = "کالاها"

    def __str__(self):
        return f"{self.name} ({self.chortke_code})"

    @property
    def display_image_url(self):
        if self.image_url:
            return self.image_url
        if self.custom_image:
            return self.custom_image.url
        from django.templatetags.static import static
        return static('storefront/media/brand-logo.png')

    @property
    def has_product_image(self):
        return bool(self.image_url or self.custom_image)

    @property
    def display_description(self):
        return self.description_override or self.description

    @property
    def category_label(self):
        return self.category.rsplit(">", 1)[-1].strip() if self.category else "قطعات خودرو"

    @property
    def stock_known(self):
        return self.stock is not None


class ProductEmbedding(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="search_embedding")
    content_hash = models.CharField(max_length=64, db_index=True)
    model_name = models.CharField(max_length=160)
    vector = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "بردار جست‌وجوی کالا"
        verbose_name_plural = "بردارهای جست‌وجوی کالاها"
