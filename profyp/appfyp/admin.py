from django.contrib import admin
# Register core models and ecommerce models
from .models import Seller, Order, Review, Performance,PerformanceSnapshot
# Register your models here.
admin.site.register(Seller)
admin.site.register(Order)
admin.site.register(Review)
admin.site.register(Performance)
admin.site.register(PerformanceSnapshot)

