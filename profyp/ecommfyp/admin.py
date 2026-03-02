from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller', 'price', 'created_at')
    list_filter = ('seller',)
    search_fields = ('name', 'description')
from django.contrib import admin

# Register your models here.
