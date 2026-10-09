from decimal import Decimal
from django.conf import settings
from store.models import Product


class Cart:
    """Simple session-based shopping cart."""

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if not cart:
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart

    @staticmethod
    def _key(product_id, options=None):
        # A product bought in two different combinations of options is two
        # separate cart lines, so the key has to include the choice. Plain
        # products (no options) keep the old key format for backwards
        # compatibility with anything already sitting in a session.
        if not options:
            return str(product_id)
        canonical = ",".join(f"{k}:{v}" for k, v in sorted(options.items()))
        return f"{product_id}|{canonical}"

    def add(self, product, quantity=1, options=None):
        """Add `quantity` of `product` (optionally with a chosen set of
        options, e.g. {'Flavor': 'Chocolate', 'Size': 'Large'}) to the
        cart, capped at available stock.

        Returns a dict describing what actually happened, since the caller
        (the AJAX view) needs to tell the user if their request was
        reduced or rejected because of low/no stock:
            {'added': int, 'requested': int, 'in_cart': int, 'stock': int}
        """
        options = options or {}
        key = self._key(product.id, options)
        price = product.sale_price if product.is_sale and product.sale_price else product.price
        if key not in self.cart:
            self.cart[key] = {
                'product_id': product.id,
                'quantity': 0,
                'price': str(price),
                'options': options,
            }

        # Stock is tracked per product, not per option combination, so
        # every combination of the same product draws from one shared pool.
        in_cart_all_combos = sum(
            item['quantity'] for k, item in self.cart.items()
            if k == str(product.id) or k.startswith(f"{product.id}|")
        )
        room_left = max(product.stock - in_cart_all_combos, 0)
        to_add = min(quantity, room_left)

        self.cart[key]['quantity'] += to_add
        self.save()

        return {
            'added': to_add,
            'requested': quantity,
            'in_cart': self.cart[key]['quantity'],
            'stock': product.stock,
        }

    def remove(self, product, options=None):
        key = self._key(product.id, options or {})
        if key in self.cart:
            del self.cart[key]
            self.save()

    def save(self):
        self.session.modified = True

    def clear(self):
        self.session[settings.CART_SESSION_ID] = {}
        self.save()

    def __iter__(self):
        # Keys look like "12" (no options) or "12|Flavor:Chocolate,Size:Large"
        # (options chosen), so pull the real product id out of each key
        # rather than using the key itself.
        product_ids = {key.split('|', 1)[0] for key in self.cart.keys()}
        products = {str(p.id): p for p in Product.objects.filter(id__in=product_ids)}
        cart = self.cart.copy()
        for key, item in cart.items():
            product_id = key.split('|', 1)[0]
            product = products.get(product_id)
            if product is None:
                # Product was deleted after being added to the cart.
                continue
            item['product'] = product
            item['options'] = item.get('options', {})
            item['options_display'] = ", ".join(
                f"{k}: {v}" for k, v in item['options'].items()
            )
            item['price'] = Decimal(item['price'])
            item['total_price'] = item['price'] * item['quantity']
            yield item

    def __len__(self):
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self):
        return sum(Decimal(item['price']) * item['quantity'] for item in self.cart.values())
