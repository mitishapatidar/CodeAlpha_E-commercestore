from django.db.models import Count, Sum

from .models import Product


def store(request):
    count = 0
    if request.user.is_authenticated:
        count = request.user.cart.aggregate(n=Sum("quantity"))["n"] or 0
    cats = Product.objects.filter(active=True).values_list("category", flat=True).distinct().order_by("category")
    return {"cart_count": count, "categories": list(cats)}
