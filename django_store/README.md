# NovaMart Store (CodeAlpha Task 1)

A simple e-commerce store: **Django** backend, **SQLite** database, frontend in plain **HTML, CSS and JavaScript**.

| Requirement | Where |
|---|---|
| Product listings | Home page with search, category filter, pagination (`shop/views.py: home`) |
| Product details page | `/product/<id>/` with specs, stock, related products |
| Shopping cart | Saved in the database per user; add (instant, via `fetch`), change quantity, delete |
| Order processing | Checkout with address form → order saved, stock reduced, cart cleared; order tracking (Placed → Processing → Shipped → Delivered); customer can cancel (stock restored); staff update status in `/admin/` |
| User registration / login | `/register/`, `/accounts/login/`, logout (Django auth, hashed passwords) |
| Database | SQLite tables: `Product`, `CartItem`, `Order`, `OrderItem`, Django `User` |

## Run

```bash
pip install django
cd django_store
python manage.py migrate
python manage.py load_products        # 300 products from ../data/products.csv
python manage.py createsuperuser      # optional: staff account for /admin/
python manage.py runserver 8080
```

Open http://localhost:8080 · admin at http://localhost:8080/admin/

## Tests

```bash
python manage.py test shop
```
