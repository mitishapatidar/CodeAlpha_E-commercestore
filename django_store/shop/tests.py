from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import CartItem, Order, Product


class StoreFlowTests(TestCase):
    def setUp(self):
        self.p = Product.objects.create(sku="SKU-1", name="Test Phone", brand="Nova", category="Smartphones",
                                        price=600, mrp=800, stock=3)
        self.user = User.objects.create_user("asha", "asha@example.com", "s3cret-pass-123", first_name="Asha")

    def test_listing_search_and_detail(self):
        r = self.client.get(reverse("home"), {"q": "phone"})
        self.assertContains(r, "Test Phone")
        r = self.client.get(reverse("product_detail", args=[self.p.pk]))
        self.assertContains(r, "₹600")

    def test_register_logs_in(self):
        r = self.client.post(reverse("register"), {"username": "ravi", "first_name": "Ravi", "email": "ravi@example.com",
                                                   "password1": "very-strong-pass-9", "password2": "very-strong-pass-9"})
        self.assertRedirects(r, reverse("home"))
        self.assertTrue(User.objects.filter(username="ravi").exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), User.objects.get(username="ravi").pk)

    def test_cart_requires_login(self):
        r = self.client.post(reverse("cart_add", args=[self.p.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r.url)

    def test_cart_respects_stock(self):
        self.client.force_login(self.user)
        for _ in range(5):
            self.client.post(reverse("cart_add", args=[self.p.pk]))
        self.assertEqual(CartItem.objects.get(user=self.user).quantity, 3)

    def test_checkout_creates_order_and_reduces_stock(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cart_add", args=[self.p.pk]))
        r = self.client.post(reverse("checkout"), {"full_name": "Asha", "phone": "9876543210", "address": "12 MG Road",
                                                   "city": "Mumbai", "pincode": "400001", "payment": "cod"})
        order = Order.objects.get(user=self.user)
        self.assertRedirects(r, reverse("order_detail", args=[order.pk]))
        self.assertEqual((order.subtotal, order.shipping, order.total), (600, 79, 679))
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 2)
        self.assertFalse(CartItem.objects.filter(user=self.user).exists())

    def test_cancel_restocks_and_other_users_cannot_see_order(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cart_add", args=[self.p.pk]))
        self.client.post(reverse("checkout"), {"full_name": "Asha", "phone": "9876543210", "address": "12 MG Road",
                                               "city": "Mumbai", "pincode": "400001", "payment": "cod"})
        order = Order.objects.get(user=self.user)
        self.client.post(reverse("order_cancel", args=[order.pk]))
        order.refresh_from_db()
        self.p.refresh_from_db()
        self.assertEqual((order.status, self.p.stock), ("cancelled", 3))
        other = User.objects.create_user("x", "x@example.com", "another-pass-456")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("order_detail", args=[order.pk])).status_code, 404)

    def test_invalid_checkout_shows_errors(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cart_add", args=[self.p.pk]))
        r = self.client.post(reverse("checkout"), {"full_name": "A", "phone": "12", "address": "x", "city": "y",
                                                   "pincode": "1", "payment": "cod"})
        self.assertContains(r, "10-digit mobile number")
        self.assertFalse(Order.objects.exists())
