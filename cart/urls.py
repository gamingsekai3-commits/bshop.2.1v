from django.urls import path
from . import views

urlpatterns = [
    path('', views.cart_detail, name='cart'),
    path('add/', views.cart_add, name='cart_add'),
    path('remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('clear/', views.cart_clear, name='cart_clear'),
    path('confirm/', views.order_confirm, name='order_confirm'),
    path('order/create/', views.order_create, name='order_create'),
    path('my-orders/', views.my_orders, name='my_orders'),
]