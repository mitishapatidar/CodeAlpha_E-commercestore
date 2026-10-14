import csv

from django.conf import settings
from django.core.management.base import BaseCommand

from shop.models import Product


class Command(BaseCommand):
    help = "Load (or refresh) the product catalogue from data/products.csv"

    def handle(self, *args, **opts):
        n = 0
        with open(settings.DATA_DIR / "products.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                Product.objects.update_or_create(sku=r["sku"], defaults={
                    "name": r["product_name"], "brand": r["brand"], "category": r["category"],
                    "description": r["description"], "price": round(float(r["price"])), "mrp": round(float(r["mrp"])),
                    "stock": int(r["stock_quantity"]), "rating": float(r["rating"] or 0),
                    "review_count": int(r["review_count"] or 0), "warranty_months": int(r["warranty_months"] or 0),
                    "returnable": r["returnable"].lower() == "true", "color": r["color"], "image_url": r.get("image_url", ""),
                    "active": r["status"] == "active",
                })
                n += 1
        self.stdout.write(self.style.SUCCESS(f"Loaded {n} products."))
