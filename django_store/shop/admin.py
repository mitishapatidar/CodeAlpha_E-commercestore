from django.contrib import admin

from .models import Order, OrderItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "category", "price", "stock", "active"]
    list_editable = ["price", "stock", "active"]
    list_filter = ["category", "active"]
    search_fields = ["name", "brand", "sku"]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "name", "price", "quantity"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "created_at", "total", "payment", "status"]
    list_editable = ["status"]
    list_filter = ["status", "payment"]
    search_fields = ["id", "user__username", "full_name", "phone"]
    inlines = [OrderItemInline]
