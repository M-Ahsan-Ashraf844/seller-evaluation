from django.urls import path
from . import views
from ecommfyp import views as ecomm_views


# app_name = "store"

urlpatterns = [

    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Seller Management
    path('sellers/', views.seller_list, name='seller_list'),
    path('sellers/<int:pk>/', views.seller_detail, name='seller_detail'),
    # Orders
    path('orders/', views.order_list, name='order_list'),


    # Reviews
    path('reviews/', views.review_list, name='review_list'),

    # Performance Ranking
    path('performance/ranking/', views.performance_ranking, name='performance_ranking'),
    
    # Reports
     path('shop/',ecomm_views.home, name='ecomerce'),
    path('reports/', views.reports, name='reports'),
    path('reports/download/', views.reports_download, name='reports_download'),

    path('create-admin/', views.create_admin),
]