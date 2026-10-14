from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CheckoutForm, RegisterForm
from .models import CartItem, Order, OrderItem, Product, cart_totals

MAX_QTY = 10


def home(request):
    q, cat = request.GET.get("q", "").strip(), request.GET.get("category", "")
    products = Product.objects.filter(active=True)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(brand__icontains=q) | Q(category__icontains=q))
    if cat:
        products = products.filter(category=cat)
    page = Paginator(products, 24).get_page(request.GET.get("page"))
    return render(request, "shop/home.html", {"page": page, "q": q, "cat": cat})


def product_detail(request, pk):
    p = get_object_or_404(Product, pk=pk, active=True)
    related = Product.objects.filter(category=p.category, active=True).exclude(pk=p.pk)[:4]
    return render(request, "shop/product_detail.html", {"p": p, "related": related})


def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome to NovaMart, {user.first_name}!")
        return redirect("home")
    return render(request, "registration/register.html", {"form": form})


def _cart(user):
    return list(user.cart.select_related("product"))


@login_required
def cart(request):
    items = _cart(request.user)
    return render(request, "shop/cart.html", {"items": items, **cart_totals(items)})


@login_required
@require_POST
def cart_add(request, pk):
    p = get_object_or_404(Product, pk=pk, active=True)
    item, _ = CartItem.objects.get_or_create(user=request.user, product=p, defaults={"quantity": 0})
    if item.quantity + 1 > min(MAX_QTY, p.stock):
        msg, ok = f"Only {min(MAX_QTY, p.stock)} of this item can be ordered.", False
        if item.quantity == 0:
            item.delete()
    else:
        item.quantity += 1
        item.save()
        msg, ok = f"Added to cart: {p.name}", True
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"ok": ok, "message": msg, "cart_count": cart_totals(_cart(request.user))["count"]})
    (messages.success if ok else messages.error)(request, msg)
    return redirect(request.POST.get("next") or "cart")


@login_required
@require_POST
def cart_update(request, pk):
    item = get_object_or_404(CartItem, user=request.user, product_id=pk)
    try:
        qty = int(request.POST.get("quantity", 1))
    except ValueError:
        qty = item.quantity
    if qty <= 0:
        item.delete()
    else:
        item.quantity = min(qty, MAX_QTY, item.product.stock)
        item.save()
    return redirect("cart")


@login_required
def checkout(request):
    items = _cart(request.user)
    if not items:
        messages.info(request, "Your cart is empty.")
        return redirect("cart")
    initial = {"full_name": request.user.get_full_name() or request.user.username}
    form = CheckoutForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=[i.product_id for i in items])}
            short = [i.product.name for i in items if locked[i.product_id].stock < i.quantity]
            if short:
                messages.error(request, "Not enough stock for: " + ", ".join(short) + ". Please update your cart.")
                return redirect("cart")
            totals = cart_totals(items)
            order = form.save(commit=False)
            order.user = request.user
            order.subtotal, order.shipping, order.total = totals["subtotal"], totals["shipping"], totals["total"]
            order.save()
            OrderItem.objects.bulk_create([
                OrderItem(order=order, product=i.product, name=i.product.name, price=i.product.price, quantity=i.quantity)
                for i in items
            ])
            for i in items:
                Product.objects.filter(pk=i.product_id).update(stock=F("stock") - i.quantity)
            request.user.cart.all().delete()
        messages.success(request, f"Order #{order.pk} placed successfully!")
        return redirect("order_detail", pk=order.pk)
    return render(request, "shop/checkout.html", {"form": form, "items": items, **cart_totals(items)})


@login_required
def orders(request):
    return render(request, "shop/orders.html", {"orders": request.user.orders.prefetch_related("items")})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk, user=request.user)
    return render(request, "shop/order_detail.html", {"order": order, "steps": Order.STEPS})


@login_required
@require_POST
def order_cancel(request, pk):
    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), pk=pk, user=request.user)
        if not order.cancellable:
            messages.error(request, "This order can no longer be cancelled.")
        else:
            for it in order.items.all():
                if it.product_id:
                    Product.objects.filter(pk=it.product_id).update(stock=F("stock") + it.quantity)
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status"])
            messages.success(request, f"Order #{order.pk} has been cancelled.")
    return redirect("order_detail", pk=pk)
