from django.conf import settings
from django.db import models

FREE_SHIPPING_AT = 1000
SHIPPING_FEE = 79


class Product(models.Model):
    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=80)
    category = models.CharField(max_length=60, db_index=True)
    description = models.TextField(blank=True)
    price = models.PositiveIntegerField()
    mrp = models.PositiveIntegerField()
    stock = models.PositiveIntegerField(default=0)
    rating = models.FloatField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    warranty_months = models.PositiveIntegerField(default=12)
    returnable = models.BooleanField(default=True)
    color = models.CharField(max_length=40, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-review_count"]

    def __str__(self):
        return self.name

    @property
    def discount(self):
        return round(100 * (self.mrp - self.price) / self.mrp) if self.mrp > self.price else 0

    @property
    def in_stock(self):
        return self.active and self.stock > 0


class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="one_line_per_product")]

    @property
    def line_total(self):
        return self.product.price * self.quantity


def cart_totals(items):
    subtotal = sum(i.line_total for i in items)
    shipping = 0 if subtotal == 0 or subtotal >= FREE_SHIPPING_AT else SHIPPING_FEE
    return {"subtotal": subtotal, "shipping": shipping, "total": subtotal + shipping,
            "count": sum(i.quantity for i in items)}


class Order(models.Model):
    class Status(models.TextChoices):
        PLACED = "placed", "Placed"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class Payment(models.TextChoices):
        COD = "cod", "Cash on delivery"
        UPI = "upi", "UPI (pay on delivery)"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLACED)
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=15)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=80)
    pincode = models.CharField(max_length=6)
    payment = models.CharField(max_length=4, choices=Payment.choices, default=Payment.COD)
    subtotal = models.PositiveIntegerField()
    shipping = models.PositiveIntegerField()
    total = models.PositiveIntegerField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk}"

    @property
    def cancellable(self):
        return self.status in (self.Status.PLACED, self.Status.PROCESSING)

    STEPS = ["placed", "processing", "shipped", "delivered"]

    @property
    def step(self):
        return self.STEPS.index(self.status) if self.status in self.STEPS else -1


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=200)
    price = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.price * self.quantity
