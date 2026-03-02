from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='ecomm_home'),
    path('product/<int:pk>/', views.product_detail, name='ecomm_product_detail'),
    path('product/<int:pk>/review/', views.add_review, name='ecomm_add_review'),
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='ecomm_add_to_cart'),
    path('cart/', views.cart_view, name='ecomm_cart'),
    path('checkout/', views.checkout, name='ecomm_checkout'),
]
