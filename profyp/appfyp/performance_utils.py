"""
Performance Calculation Module
E-Commerce Seller Performance Evaluation System

This module handles all performance-related calculations and snapshot creation.
Separated from views for better architecture and reusability.
"""

from django.db.models import Avg, Sum, Count, Q
from django.utils import timezone
from datetime import date, timedelta
from .models import Seller, Order, Review, Performance, PerformanceSnapshot


# ============================================
# PERFORMANCE CALCULATION FUNCTION
# ============================================
def calculate_performance(seller):
    """
    Calculates comprehensive performance metrics for a seller.
    
    Metrics:
    - total_orders: count of all orders
    - avg_rating: mean customer rating (1‑5)
    - delivery_rate: % of orders marked as 'Delivered'
    - return_rate: % of orders returned
    - performance_score: weighted composite (rating 40%, delivery 40%, non‑return 20%)
    
    Returns:
        Performance object with updated metrics
    """
    total_orders = seller.orders.count()
    if total_orders == 0:
        # No orders → default zero metrics
        performance, _ = Performance.objects.update_or_create(
            seller=seller,
            defaults={
                'total_orders': 0,
                'average_rating': 0.0,
                'delivery_rate': 0.0,
                'return_rate': 0.0,
                'performance_score': 0.0
            }
        )
        return performance

    # Core counts
    delivered_orders = seller.orders.filter(delivery_status='Delivered').count()
    returned_orders = seller.orders.filter(is_returned=True).count()
    avg_rating = seller.reviews.aggregate(avg=Avg('rating'))['avg'] or 0.0

    # Rates (percentages)
    delivery_rate = (delivered_orders / total_orders) * 100.0
    return_rate = (returned_orders / total_orders) * 100.0

    # Normalise rating to 0‑100 scale
    normalized_rating = (avg_rating / 5.0) * 100.0

    # Performance score: rating (40%) + delivery (40%) + non‑return (20%)
    performance_score = (
        normalized_rating * 0.4 +
        delivery_rate * 0.4 +
        (100.0 - return_rate) * 0.2
    )
    performance_score = max(0.0, performance_score)   # no negative scores

    # Update or create Performance record
    performance, _ = Performance.objects.update_or_create(
        seller=seller,
        defaults={
            'total_orders': total_orders,
            'average_rating': round(avg_rating, 2),
            'delivery_rate': round(delivery_rate, 2),
            'return_rate': round(return_rate, 2),
            'performance_score': round(performance_score, 2)
        }
    )
    return performance


# ============================================
# SNAPSHOT CREATION FUNCTION
# ============================================
def create_daily_snapshot(seller, snapshot_date=None):
    """
    Creates a daily performance snapshot for a seller.
    Only creates snapshots for dates that are at least 7 days old,
    allowing orders to reach final delivery/return status.

    Args:
        seller: Seller instance
        snapshot_date: target date (defaults to today)

    Returns:
        PerformanceSnapshot object or None if date is too recent
    """
    if snapshot_date is None:
        snapshot_date = timezone.now().date()

    # --- Maturity guard: do not create snapshots for recent dates ---
    maturity_delay = 7   # days
    if snapshot_date > timezone.now().date() - timedelta(days=maturity_delay):
        # Not enough time for orders to settle → skip creation
        return None

    # Orders placed on the snapshot date
    orders_on_date = seller.orders.filter(order_date=snapshot_date)
    # Reviews left on that date
    reviews_on_date = seller.reviews.filter(review_date=snapshot_date)

    # Basic aggregates
    order_count = orders_on_date.count()
    placed_sales = orders_on_date.aggregate(total=Sum('total_amount'))['total'] or 0.0
    avg_rating = reviews_on_date.aggregate(avg=Avg('rating'))['avg'] or 0.0

    # Delivery and return counts (using final statuses)
    delivered_orders = orders_on_date.filter(delivery_status='Delivered').count()
    delivered_sales = orders_on_date.filter(delivery_status='Delivered').aggregate(
        total=Sum('total_amount')
    )['total'] or 0.0

    returned_orders = orders_on_date.filter(is_returned=True).count()

    # Rates (percentages) – avoid division by zero
    delivery_rate = (delivered_orders / order_count * 100.0) if order_count > 0 else 0.0
    return_ratio = (returned_orders / order_count * 100.0) if order_count > 0 else 0.0

    # Performance score (same formula as calculate_performance)
    normalized_rating = (avg_rating / 5.0) * 100.0 if avg_rating > 0 else 0.0
    performance_score = (
        normalized_rating * 0.4 +
        delivery_rate * 0.4 +
        (100.0 - return_ratio) * 0.2
    )
    performance_score = max(0.0, performance_score)

    # Create or update snapshot
    snapshot, _ = PerformanceSnapshot.objects.update_or_create(
        seller=seller,
        date=snapshot_date,
        defaults={
            'sales_volume': round(placed_sales, 2),
            'order_count': order_count,
            'avg_rating': round(avg_rating, 2),
            'delivery_rate': round(delivery_rate, 2),
            'return_ratio': round(return_ratio, 2),
            'delivered_sales': round(delivered_sales, 2),
            'delivered_orders': delivered_orders,
            'performance_score': round(performance_score, 2)
        }
    )
    return snapshot


# ============================================
# BATCH SNAPSHOT CREATION
# ============================================
def create_snapshots_for_all_sellers(snapshot_date=None):
    """
    Creates daily snapshots for all sellers.
    Intended for scheduled tasks (e.g., daily cron job).
    Only creates snapshots for dates that satisfy the maturity delay.

    Args:
        snapshot_date: target date (defaults to today)

    Returns:
        Number of snapshots successfully created
    """
    if snapshot_date is None:
        snapshot_date = timezone.now().date()

    sellers = Seller.objects.all()
    created_count = 0
    for seller in sellers:
        try:
            if create_daily_snapshot(seller, snapshot_date) is not None:
                created_count += 1
        except Exception as e:
            # Log error (in production use proper logging)
            print(f"Error creating snapshot for {seller.name}: {e}")
            continue
    return created_count


# ============================================
# PERFORMANCE AGGREGATION HELPERS
# ============================================
def get_performance_trend(seller, days=30):
    """
    Returns snapshots for the last `days` days for a given seller.
    """
    start_date = timezone.now().date() - timedelta(days=days)
    return seller.snapshots.filter(date__gte=start_date).order_by('date')


def get_system_wide_stats():
    """
    Calculates system‑wide performance statistics.
    """
    total_orders = Order.objects.count()
    total_revenue = Order.objects.aggregate(total=Sum('total_amount'))['total'] or 0.0
    returns_revenue = Order.objects.filter(is_returned=True).aggregate(
        total=Sum('total_amount')
    )['total'] or 0.0
    net_revenue = total_revenue - returns_revenue

    delivered_and_not_returned = Order.objects.filter(
        delivery_status='Delivered', is_returned=False
    ).count()
    non_returned_orders = Order.objects.filter(is_returned=False).count()
    delivery_rate = (delivered_and_not_returned / non_returned_orders * 100.0) if non_returned_orders > 0 else 0.0

    returned_count = Order.objects.filter(is_returned=True).count()
    return_rate = (returned_count / total_orders * 100.0) if total_orders > 0 else 0.0

    avg_rating = Review.objects.aggregate(avg=Avg('rating'))['avg'] or 0.0

    return {
        'total_orders': total_orders,
        'total_revenue': round(total_revenue, 2),
        'returns_revenue': round(returns_revenue, 2),
        'net_revenue': round(net_revenue, 2),
        'delivery_rate': round(delivery_rate, 2),
        'return_rate': round(return_rate, 2),
        'avg_rating': round(avg_rating, 2),
    }