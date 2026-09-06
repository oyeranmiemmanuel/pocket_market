from django.contrib import admin

from .models import Category, Product, ProductColorVariant, ProductImage, ProductSizeVariant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_deleted"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]
    list_per_page = 50


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    max_num = ProductImage.MAX_IMAGES


class ProductColorVariantInline(admin.TabularInline):
    model = ProductColorVariant
    extra = 1


class ProductSizeVariantInline(admin.TabularInline):
    model = ProductSizeVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "seller", "price", "stock_display", "product_type", "is_active"]
    list_filter = ["product_type", "is_active", "category"]
    search_fields = ["name", "description", "seller__store_name"]
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["seller"]
    inlines = [ProductImageInline, ProductColorVariantInline, ProductSizeVariantInline]
    list_per_page = 25
    list_select_related = ["category", "seller"]

    fieldsets = (
        (None, {
            "fields": ("name", "slug", "category", "seller", "description"),
        }),
        ("Pricing & Stock", {
            "fields": ("price", "stock", "commission_rate"),
        }),
        ("Product Type", {
            "fields": ("product_type", "image", "digital_file"),
        }),
        ("Visibility", {
            "fields": ("is_active",),
        }),
    )

    @admin.display(description="Stock", ordering="stock")
    def stock_display(self, obj):
        if obj.stock == 0:
            return "Out of stock"
        if obj.stock <= 5:
            return f"{obj.stock} (low)"
        return obj.stock