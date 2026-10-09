import json
from urllib.parse import unquote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from store.models import Product
from store.translations import t
from .cart import Cart
from .models import Order, OrderItem

def cart_detail(request):
    cart = Cart(request)
    return render(request, 'cart.html', {'cart': cart})


def cart_add(request):
    """Handles the AJAX 'add to cart' request sent from product_detail.html."""
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        try:
            qty = int(request.POST.get('product_qty'))
        except (TypeError, ValueError):
            qty = 1
        # Product.active: a product switched off in the admin can no longer
        # be added to a cart, same as if it had been deleted.
        product = get_object_or_404(Product.active, id=product_id)

        # Only accept options that are actually active choices on this
        # product, so a tampered request can't stamp an arbitrary value
        # onto the order.
        selected_options = {}
        try:
            submitted = json.loads(request.POST.get('options', '') or '{}')
        except (TypeError, ValueError):
            submitted = {}
        if isinstance(submitted, dict):
            valid_by_type = {}
            for opt in product.options.filter(is_active=True):
                valid_by_type.setdefault(opt.option_type, set()).add(opt.value)
            for option_type, chosen_value in submitted.items():
                if option_type in valid_by_type and chosen_value in valid_by_type[option_type]:
                    selected_options[option_type] = chosen_value

        if product.stock <= 0:
            return JsonResponse({
                'error': 'out_of_stock',
                'message': t(request, 'msg_out_of_stock'),
                'cart_qty': len(cart),
            }, status=400)

        result = cart.add(product=product, quantity=qty, options=selected_options)

        if result['added'] < result['requested']:
            # Stock ran out mid-add; tell the user how many actually made it in.
            message = t(request, 'msg_insufficient_stock').format(stock=result['stock'])
            return JsonResponse({
                'warning': 'insufficient_stock',
                'message': message,
                'cart_qty': len(cart),
                'added': result['added'],
            })

        return JsonResponse({'cart_qty': len(cart), 'added': result['added']})
    return JsonResponse({'error': 'Invalid request'}, status=400)


def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    options = {}
    raw = request.GET.get('options', '')
    for pair in raw.split(','):
        if ':' in pair:
            key, value = pair.split(':', 1)
            options[unquote(key)] = unquote(value)
    cart.remove(product, options=options)
    return redirect('cart')


def cart_clear(request):
    cart = Cart(request)
    cart.clear()
    return redirect('cart')

def order_confirm(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.error(request, t(request, 'msg_cart_empty'))
        return redirect('cart')

    return render(request, 'order_confirm.html', {'cart': cart})


def order_create(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.error(request, t(request, 'msg_cart_empty'))
        return redirect('cart')

    if request.method == 'POST':
        # Re-check stock at the moment of purchase (not just at add-to-cart
        # time) since it may have changed while the cart was sitting idle,
        # and lock the rows so two simultaneous checkouts can't both
        # succeed for the last unit of a product.
        with transaction.atomic():
            products_by_id = {
                str(p.id): p
                for p in Product.objects.select_for_update().filter(
                    id__in=[item['product'].id for item in cart]
                )
            }

            for item in cart:
                product = products_by_id.get(str(item['product'].id))
                if product is None or product.stock < item['quantity']:
                    name = product.name if product else item['product'].name
                    available = product.stock if product else 0
                    messages.error(
                        request,
                        t(request, 'msg_insufficient_stock').format(stock=available) + f' ({name})',
                    )
                    return redirect('cart')

            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                name=request.POST.get('name', ''),
                phone=request.POST.get('phone', ''),
                address=request.POST.get('address', ''),
            )
            for item in cart:
                product = products_by_id[str(item['product'].id)]
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    price=item['price'],
                    quantity=item['quantity'],
                    options=item.get('options_display', ''),
                )
                product.stock -= item['quantity']
                product.save(update_fields=['stock'])

        cart.clear()
        messages.success(request, t(request, 'msg_order_confirmed'))
        return redirect('my_orders')

    return redirect('order_confirm')


@login_required
def my_orders(request):
    # Archived (inactive) orders stay in the database for reporting but are
    # not listed back to the customer.
    orders = (Order.active.filter(user=request.user)
              .select_related('delivery', 'delivery__driver__user')
              .prefetch_related('items'))
    return render(request, 'my_orders.html', {'orders': orders})