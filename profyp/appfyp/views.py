from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum, Q, F
from django.utils import timezone
from django.utils.safestring import mark_safe
from datetime import datetime, timedelta, date
import json
from collections import defaultdict
from .models import (
    Seller, Order, Review, Performance, PerformanceSnapshot,
   
)
from appfyp.report_utils import generate_seller_pdf_report
from django.db.utils import OperationalError
from .performance_utils import (
    calculate_performance,
    create_daily_snapshot,
    get_performance_trend,
    get_system_wide_stats
)


@login_required
def dashboard(request):
    
    """
    E-Commerce Seller Performance Dashboard
    Comprehensive overview of seller performance metrics and KPIs
    
    Displays:
    - Total sellers, orders, reviews (high-level metrics)
    - Recent orders activity
    - Top performing sellers
    - E-commerce specific analytics
    """
    
    # ============================================
    # HIGH-LEVEL KPIs (Overall System Metrics)
    # ============================================
    total_sellers = Seller.objects.count()
    total_orders = Order.objects.count()
    total_reviews = Review.objects.count()
    
    # Active sellers count (E-Commerce status tracking)
    active_sellers = Seller.objects.filter(status='Active').count()
    
    # ============================================
    # E-COMMERCE SPECIFIC METRICS
    # ============================================
    # Total revenue (sum of all order amounts)
    # Total revenue (gross) and net revenue after returns
    total_revenue = Order.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    returns_revenue = Order.objects.filter(is_returned=True).aggregate(total=Sum('total_amount'))['total'] or 0
    net_revenue = total_revenue - returns_revenue

    # Average order value (AOV) - use net revenue divided by non-returned orders
    non_returned_orders = Order.objects.filter(is_returned=False).count()
    avg_order_value = (net_revenue / non_returned_orders) if non_returned_orders > 0 else 0
    
    # Delivery success rate (system-wide)
    # Count deliveries that were not returned
    delivered_and_not_returned = Order.objects.filter(delivery_status='Delivered', is_returned=False).count()
    # Return rate (system-wide)
    returned_count = Order.objects.filter(is_returned=True).count()
    system_return_rate = (
        (returned_count / total_orders * 100) if total_orders > 0 else 0
    )
    # Denominator: non-returned orders (only orders that can be considered successful)
    deliverable_orders = Order.objects.filter(is_returned=False).count()
    delivery_success_rate = (
    (delivered_and_not_returned / deliverable_orders * 100)
    if deliverable_orders > 0 else 0
)
    
    
    
    # Average customer rating (system-wide)
    avg_system_rating = Review.objects.aggregate(avg=Avg('rating'))['avg'] or 0
    
    # ============================================
    # RECENT ACTIVITY (Last 30 days)
    # ============================================
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    
    recent_orders_count = Order.objects.filter(
        order_date__gte=thirty_days_ago
    ).count()
    
    # Recent orders for dashboard widget (safe when tables missing)
    try:
        recent_orders = (
            Order.objects
            .select_related('seller')
            .order_by('-order_date')[:10]
        )
    except OperationalError:
        recent_orders = []
    
    # ============================================
    # PERFORMANCE RANKINGS
    # ============================================
    # Request filters for seller list inside dashboard
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    # Ensure all seller performances are up to date
    sellers = Seller.objects.all()

    # Apply optional filters from the dashboard UI
    if search_query:
        sellers = sellers.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    if status_filter:
        sellers = sellers.filter(status=status_filter)

    for seller in sellers:
        try:
            calculate_performance(seller)
        except Exception:
            pass

    # Top / bottom performers by score (safe)
    try:
        top_performances = (
            Performance.objects
            .select_related('seller')
            .filter(seller__status='Active')
            .order_by('-performance_score')[:5]
        )

        bottom_performances = (
            Performance.objects
            .select_related('seller')
            .filter(seller__status='Active')
            .order_by('performance_score')[:5]
        )
    except OperationalError:
        top_performances = []
        bottom_performances = []
    # (performance already calculated above for filtered sellers)
    
    # ============================================
    # SORTING (optional - can be added via GET params)
    # ============================================
    sort_by = request.GET.get('sort', 'id')
    if sort_by == 'name':
        sellers = sellers.order_by('name')
    elif sort_by == 'status':
        sellers = sellers.order_by('status', 'name')
    elif sort_by == 'created':
        sellers = sellers.order_by('-created_at')
    else:
        sellers = sellers.order_by('id')
    
    # ============================================
    # CONTEXT DATA
    # ============================================
    # Provide simple trend data for charts (safe when DB empty)
    try:
        revenue_qs = (
            Order.objects
            .filter(order_date__gte=thirty_days_ago)
            .values('order_date')
            .annotate(revenue=Sum('total_amount'))
            .order_by('order_date')
        )
        revenue_trend = [{'order_date': r['order_date'].isoformat(), 'revenue': float(r['revenue'] or 0)} for r in revenue_qs]

        orders_qs = (
            Order.objects
            .filter(order_date__gte=thirty_days_ago)
            .values('order_date')
            .annotate(count=Count('id'))
            .order_by('order_date')
        )
        orders_trend = [{'order_date': o['order_date'].isoformat(), 'count': int(o['count'] or 0)} for o in orders_qs]

        try:
            top_5_performers = list(top_performances.values('seller__name', 'performance_score')) if hasattr(top_performances, 'values') else []
            bottom_5_performers = list(bottom_performances.values('seller__name', 'performance_score')) if hasattr(bottom_performances, 'values') else []
        except Exception:
            top_5_performers = []
            bottom_5_performers = []
            bottom_5_performers = list(bottom_performances.values('seller__name', 'performance_score')) if hasattr(bottom_performances, 'values') else []
    except OperationalError:
        revenue_trend = []
        orders_trend = []
        top_5_performers = []
        bottom_5_performers = []
    context = {
        'sellers': sellers,
        'search_query': search_query,
        'status_filter': status_filter,
        'status_choices': Seller.STATUS_CHOICES,
        # High-level KPIs
        'total_sellers': total_sellers,
        'active_sellers': active_sellers,
        'total_orders': total_orders,
        'total_reviews': total_reviews,
        'total_revenue': round(total_revenue, 2),
        'net_revenue': round(net_revenue, 2),
        'avg_order_value': round(avg_order_value, 2),
        'delivery_success_rate': round(delivery_success_rate, 2),
        'system_return_rate': round(system_return_rate, 2),
        'avg_system_rating': round(avg_system_rating, 2),
        # Recent activity & rankings
        'recent_orders': recent_orders,
        'recent_orders_count': recent_orders_count,
        'top_performances': top_performances,
        'bottom_performances': bottom_performances,
        # chart/trend variables used in template
        'revenue_trend': mark_safe(json.dumps(revenue_trend)),
        'orders_trend': mark_safe(json.dumps(orders_trend)),
        'top_5_performers': mark_safe(json.dumps(top_5_performers)),
        'bottom_5_performers': mark_safe(json.dumps(bottom_5_performers)),
    }

    return render(request, 'dashboard.html', context)


# ==============================================
# Seller List View
# ==============================================
def seller_report_pdf(request, seller_id):
    """
    Downloads a PDF performance report for the given seller.
    URL: /sellers/<seller_id>/report/
    """
    seller = get_object_or_404(Seller, pk=seller_id)
    return generate_seller_pdf_report(seller)

@login_required
def seller_list(request):
    """
    E-Commerce Seller List View with Filtering & Search
    Displays all sellers with performance metrics
    """
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    sellers = Seller.objects.all()

    if search_query:
        sellers = sellers.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    if status_filter:
        sellers = sellers.filter(status=status_filter)

    for seller in sellers:
        calculate_performance(seller)

    sort_by = request.GET.get('sort', 'id')
    if sort_by == 'name':
        sellers = sellers.order_by('name')
    elif sort_by == 'status':
        sellers = sellers.order_by('status', 'name')
    elif sort_by == 'created':
        sellers = sellers.order_by('-created_at')
    else:
        sellers = sellers.order_by('id')

    context = {
        'sellers': sellers,
        'search_query': search_query,
        'status_filter': status_filter,
        'status_choices': Seller.STATUS_CHOICES,
    }

    return render(request, 'seller_list.html', context)


# ==============================================
# Seller Detail View
# ==============================================

@login_required
def seller_detail(request, pk):
    """
    E-Commerce Seller Detail View
    Comprehensive seller performance evaluation
    
    Displays:
    - Seller profile information
    - Real-time performance metrics
    - Order history with filtering
    - Customer reviews and ratings
    - E-commerce specific analytics
    """
    
    seller = get_object_or_404(Seller, pk=pk)
    
    # ============================================
    # PERFORMANCE CALCULATION
    # ============================================
    # Recalculate performance to ensure latest metrics
    performance = calculate_performance(seller)
    
    # ============================================
    # ORDER DATA WITH FILTERING
    # ============================================
    orders = seller.orders.all()
    
    # Filter by delivery status
    delivery_filter = request.GET.get('delivery_status', '')
    if delivery_filter:
        orders = orders.filter(delivery_status=delivery_filter)
    
    # Filter by return status
    return_filter = request.GET.get('returned', '')
    if return_filter == 'yes':
        orders = orders.filter(is_returned=True)
    elif return_filter == 'no':
        orders = orders.filter(is_returned=False)
    
    # Date range filtering (optional)
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        orders = orders.filter(order_date__gte=date_from)
    if date_to:
        orders = orders.filter(order_date__lte=date_to)
    
    # Order by date (newest first)
    orders = orders.order_by('-order_date')
    
    # ============================================
    # E-COMMERCE METRICS FOR THIS SELLER
    # ============================================
    # Total revenue for this seller
    seller_revenue = orders.aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # Average order value
    seller_avg_order_value = orders.aggregate(
        avg=Avg('total_amount')
    )['avg'] or 0
    
    # Orders by status breakdown
    orders_by_status = orders.values('delivery_status').annotate(
        count=Count('id')
    )
    
    # ============================================
    # REVIEW DATA
    # ============================================
    reviews = seller.reviews.all().order_by('-review_date')
    
    # Rating distribution
    rating_distribution = reviews.values('rating').annotate(
        count=Count('id')
    ).order_by('-rating')
    
    # ============================================
    # RECENT ACTIVITY (Last 30 days)
    # ============================================
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    recent_orders_count = orders.filter(
        order_date__gte=thirty_days_ago
    ).count()
    
    recent_reviews_count = reviews.filter(
        review_date__gte=thirty_days_ago
    ).count()
    
    # ============================================
    # CONTEXT DATA
    # ============================================
    context = {
        'seller': seller,
        'orders': orders,
        'reviews': reviews,
        'performance': performance,
        
        # E-Commerce Metrics
        'seller_revenue': round(seller_revenue, 2),
        'seller_avg_order_value': round(seller_avg_order_value, 2),
        'orders_by_status': orders_by_status,
        'rating_distribution': rating_distribution,
        'recent_orders_count': recent_orders_count,
        'recent_reviews_count': recent_reviews_count,
        
        # Filter values for template
        'delivery_filter': delivery_filter,
        'return_filter': return_filter,
        'date_from': date_from,
        'date_to': date_to,
        'delivery_status_choices': Order.DELIVERY_STATUS,
    }
    
    return render(request, 'seller_detail.html', context)


# ==============================================
# Order List View
# ==============================================

@login_required
def order_list(request):
    """
    E-Commerce Order Management View
    Comprehensive order listing with filtering and search
    
    Features:
    - Filter by seller
    - Filter by delivery status
    - Filter by return status
    - Date range filtering
    - Search by order ID or seller name
    """
    
    # ============================================
    # BASE QUERYSET
    # ============================================
    orders = Order.objects.select_related('seller').all()
    
    # ============================================
    # FILTERING FUNCTIONALITY
    # ============================================
    # Search by order ID or seller name
    search_query = request.GET.get('search', '')
    if search_query:
        try:
            # Try to search by order ID
            order_id = int(search_query)
            orders = orders.filter(id=order_id)
        except ValueError:
            # Search by seller name
            orders = orders.filter(seller__name__icontains=search_query)
    
    # Filter by seller
    seller_filter = request.GET.get('seller', '')
    if seller_filter:
        orders = orders.filter(seller_id=seller_filter)
    
    # Filter by delivery status
    delivery_filter = request.GET.get('delivery_status', '')
    if delivery_filter:
        orders = orders.filter(delivery_status=delivery_filter)
    
    # Filter by return status
    return_filter = request.GET.get('returned', '')
    if return_filter == 'yes':
        orders = orders.filter(is_returned=True)
    elif return_filter == 'no':
        orders = orders.filter(is_returned=False)
    
    # Date range filtering
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        orders = orders.filter(order_date__gte=date_from)
    if date_to:
        orders = orders.filter(order_date__lte=date_to)
    
    # ============================================
    # SORTING
    # ============================================
    sort_by = request.GET.get('sort', '-order_date')
    if sort_by in ['order_date', '-order_date', 'total_amount', '-total_amount']:
        orders = orders.order_by(sort_by)
    else:
        orders = orders.order_by('-order_date')
    
    # ============================================
    # STATISTICS
    # ============================================
    total_revenue = orders.aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    orders_by_status = orders.values('delivery_status').annotate(
        count=Count('id')
    )
    
    # ============================================
    # CONTEXT DATA
    # ============================================
    context = {
        'orders': orders,
        'search_query': search_query,
        'seller_filter': seller_filter,
        'delivery_filter': delivery_filter,
        'return_filter': return_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_revenue': round(total_revenue, 2),
        'orders_by_status': orders_by_status,
        'sellers': Seller.objects.all().order_by('name'),
        'delivery_status_choices': Order.DELIVERY_STATUS,
    }
    
    return render(request, 'order_list.html', context)



# ==============================================
# Review List View
# ==============================================

@login_required
def review_list(request):
    """
    E-Commerce Review Management View
    Customer feedback and rating analysis
    
    Features:
    - Filter by seller
    - Filter by rating (1-5 stars)
    - Search reviews by comment text
    - Sort by date or rating
    """
    
    # ============================================
    # BASE QUERYSET
    # ============================================
    reviews = Review.objects.select_related('seller').all()
    
    # ============================================
    # FILTERING FUNCTIONALITY
    # ============================================
    # Filter by seller
    seller_filter = request.GET.get('seller', '')
    if seller_filter:
        reviews = reviews.filter(seller_id=seller_filter)
    
    # Filter by rating
    rating_filter = request.GET.get('rating', '')
    if rating_filter:
        try:
            rating_value = int(rating_filter)
            reviews = reviews.filter(rating=rating_value)
        except ValueError:
            pass
    
    # Search by comment text
    search_query = request.GET.get('search', '')
    if search_query:
        reviews = reviews.filter(comment__icontains=search_query)
    
    # Date range filtering
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        reviews = reviews.filter(review_date__gte=date_from)
    if date_to:
        reviews = reviews.filter(review_date__lte=date_to)
    
    # ============================================
    # SORTING
    # ============================================
    sort_by = request.GET.get('sort', '-review_date')
    if sort_by in ['review_date', '-review_date', 'rating', '-rating']:
        reviews = reviews.order_by(sort_by)
    else:
        reviews = reviews.order_by('-review_date')
    
    # ============================================
    # STATISTICS
    # ============================================
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    
    rating_distribution = reviews.values('rating').annotate(
        count=Count('id')
    ).order_by('-rating')
    
    # ============================================
    # CONTEXT DATA
    # ============================================
    context = {
        'reviews': reviews,
        'seller_filter': seller_filter,
        'rating_filter': rating_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'avg_rating': round(avg_rating, 2),
        'rating_distribution': rating_distribution,
        'sellers': Seller.objects.all().order_by('name'),
        'rating_choices': [(i, f'{i} Star{"s" if i > 1 else ""}') for i in range(1, 6)],
    }
    
    return render(request, 'review_list.html', context)


# ==============================================
# Performance Ranking View
# ==============================================

@login_required
def performance_ranking(request):
    """
    E-Commerce Seller Performance Ranking View
    Comprehensive ranking system for seller evaluation
    
    Features:
    - Ranked by performance score (descending)
    - Filter by seller status
    - Sort by various metrics
    - Performance tier categorization
    """
    
    # ============================================
    # BASE QUERYSET
    # ============================================
    sellers = Seller.objects.all()
    
    # ============================================
    # PERFORMANCE CALCULATION
    # ============================================
    # Ensure all seller performances are up to date
    for seller in sellers:
        calculate_performance(seller)
    
    # ============================================
    # FILTERING
    # ============================================
    performances = Performance.objects.select_related('seller').all()
    
    # Filter by seller status
    status_filter = request.GET.get('status', '')
    if status_filter:
        performances = performances.filter(seller__status=status_filter)
    else:
        # Default: show only active sellers
        performances = performances.filter(seller__status='Active')
    
    # Search by seller name
    search_query = request.GET.get('search', '')
    if search_query:
        performances = performances.filter(
            seller__name__icontains=search_query
        )
    
    # ============================================
    # SORTING
    # ============================================
    sort_by = request.GET.get('sort', '-performance_score')
    valid_sorts = {
        '-performance_score': '-performance_score',
        'performance_score': 'performance_score',
        '-average_rating': '-average_rating',
        'average_rating': 'average_rating',
        '-delivery_rate': '-delivery_rate',
        'delivery_rate': 'delivery_rate',
        '-total_orders': '-total_orders',
        'total_orders': 'total_orders',
    }
    if sort_by in valid_sorts:
        performances = performances.order_by(valid_sorts[sort_by])
    else:
        performances = performances.order_by('-performance_score')
    
    # ============================================
    # PERFORMANCE TIER CATEGORIZATION
    # ============================================
    # Categorize sellers into performance tiers
    # Top Tier: Score >= 70
    # Mid Tier: Score 40-69
    # Low Tier: Score < 40
    top_tier = performances.filter(performance_score__gte=70)
    mid_tier = performances.filter(
        performance_score__gte=40,
        performance_score__lt=70
    )
    low_tier = performances.filter(performance_score__lt=40)
    
    # ============================================
    # STATISTICS
    # ============================================
    total_sellers_ranked = performances.count()
    avg_performance_score = performances.aggregate(
        avg=Avg('performance_score')
    )['avg'] or 0
    
    # ============================================
    # CONTEXT DATA
    # ============================================
    context = {
        'performances': performances,
        'status_filter': status_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'top_tier': top_tier,
        'mid_tier': mid_tier,
        'low_tier': low_tier,
        'total_sellers_ranked': total_sellers_ranked,
        'avg_performance_score': round(avg_performance_score, 2),
        'status_choices': Seller.STATUS_CHOICES,
    }
    
    return render(request, 'ranking.html', context)


@login_required
def reports(request):
    """
    E-Commerce Performance Reports View
    Comprehensive analytics and reporting based on PerformanceSnapshot data
    
    Features:
    - Performance trends over time
    - Sales volume analysis
    - Delivery and return rate trends
    - Top/bottom performers analysis
    - Date range filtering
    """
    
    # ============================================
    # DATE RANGE FILTERING
    # ============================================
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Default to last 30 days if no dates provided
    if not date_from:
        date_from = (timezone.now().date() - timedelta(days=30)).isoformat()
    if not date_to:
        date_to = timezone.now().date().isoformat()
    
    try:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        date_from_obj = timezone.now().date() - timedelta(days=30)
        date_to_obj = timezone.now().date()
    
    # ============================================
    # DIRECT REPORT DATA (NO SNAPSHOTS)
    # ============================================
    seller_filter = request.GET.get('seller', '')
    seller_id = None
    if seller_filter:
        try:
            seller_id = int(seller_filter)
        except ValueError:
            seller_id = None

    orders = Order.objects.filter(
        order_date__gte=date_from_obj,
        order_date__lte=date_to_obj
    )
    reviews = Review.objects.filter(
        review_date__gte=date_from_obj,
        review_date__lte=date_to_obj
    )
    if seller_id:
        orders = orders.filter(seller_id=seller_id)
        reviews = reviews.filter(seller_id=seller_id)

    total_sales_volume = float(orders.aggregate(total=Sum('total_amount'))['total'] or 0)
    total_orders_in_period = int(orders.count())
    total_delivered_orders = int(orders.filter(delivery_status='Delivered').count())
    total_returned_orders = int(orders.filter(is_returned=True).count())
    avg_rating = float(reviews.aggregate(avg=Avg('rating'))['avg'] or 0)

    avg_delivery_rate = (total_delivered_orders / total_orders_in_period * 100) if total_orders_in_period > 0 else 0
    avg_return_ratio = (total_returned_orders / total_orders_in_period * 100) if total_orders_in_period > 0 else 0
    normalized_rating = (avg_rating / 5.0) * 100 if avg_rating > 0 else 0
    avg_performance_score = (
        normalized_rating * 0.4 +
        avg_delivery_rate * 0.4 +
        (100.0 - avg_return_ratio) * 0.2
    ) if total_orders_in_period > 0 else 0

    daily_orders_qs = orders.values('order_date').annotate(
        total_sales=Sum('total_amount'),
        total_orders=Count('id'),
        delivered_orders=Count('id', filter=Q(delivery_status='Delivered')),
        returned_orders=Count('id', filter=Q(is_returned=True))
    ).order_by('order_date')
    daily_reviews_map = {
        row['review_date']: float(row['avg_rating'] or 0)
        for row in reviews.values('review_date').annotate(avg_rating=Avg('rating'))
    }

    daily_sales = []
    performance_trend = []
    delivery_trend = []
    for row in daily_orders_qs:
        report_date = row['order_date']
        day_orders = int(row['total_orders'] or 0)
        day_delivered = int(row['delivered_orders'] or 0)
        day_returned = int(row['returned_orders'] or 0)
        day_delivery_rate = (day_delivered / day_orders * 100) if day_orders > 0 else 0
        day_return_ratio = (day_returned / day_orders * 100) if day_orders > 0 else 0
        day_rating = daily_reviews_map.get(report_date, 0.0)
        day_norm_rating = (day_rating / 5.0) * 100 if day_rating > 0 else 0
        day_score = (
            day_norm_rating * 0.4 +
            day_delivery_rate * 0.4 +
            (100.0 - day_return_ratio) * 0.2
        ) if day_orders > 0 else 0

        daily_sales.append({
            'date': report_date.isoformat(),
            'total_sales': float(row['total_sales'] or 0),
            'total_orders': day_orders
        })
        performance_trend.append({'date': report_date.isoformat(), 'avg_score': day_score})
        delivery_trend.append({'date': report_date.isoformat(), 'avg_delivery': day_delivery_rate})

    seller_stats_qs = orders.values('seller_id', 'seller__name').annotate(
        total_sales=Sum('total_amount'),
        total_orders=Count('id'),
        delivered_orders=Count('id', filter=Q(delivery_status='Delivered')),
        returned_orders=Count('id', filter=Q(is_returned=True))
    )
    seller_rating_map = {
        row['seller_id']: float(row['avg_rating'] or 0)
        for row in reviews.values('seller_id').annotate(avg_rating=Avg('rating'))
    }
    top_sellers = []
    for row in seller_stats_qs:
        s_orders = int(row['total_orders'] or 0)
        s_delivery = (int(row['delivered_orders'] or 0) / s_orders * 100) if s_orders > 0 else 0
        s_returns = (int(row['returned_orders'] or 0) / s_orders * 100) if s_orders > 0 else 0
        s_rating = seller_rating_map.get(row['seller_id'], 0.0)
        s_norm_rating = (s_rating / 5.0) * 100 if s_rating > 0 else 0
        s_score = (s_norm_rating * 0.4 + s_delivery * 0.4 + (100.0 - s_returns) * 0.2) if s_orders > 0 else 0
        top_sellers.append({
            'seller__name': row['seller__name'],
            'seller__id': row['seller_id'],
            'avg_score': s_score,
            'total_sales': float(row['total_sales'] or 0),
            'total_orders': s_orders
        })
    top_sellers = sorted(top_sellers, key=lambda x: x['avg_score'], reverse=True)[:10]

    # Keep template keys unchanged: this is now daily metrics, not snapshots.
    snapshot_list = []
    daily_seller_orders_qs = orders.values('order_date', 'seller_id', 'seller__name').annotate(
        sales_volume=Sum('total_amount'),
        order_count=Count('id'),
        delivered_sales=Sum('total_amount', filter=Q(delivery_status='Delivered')),
        delivered_orders=Count('id', filter=Q(delivery_status='Delivered')),
        returned_orders=Count('id', filter=Q(is_returned=True)),
    ).order_by('order_date', 'seller__name')
    daily_seller_reviews_map = {
        (row['review_date'], row['seller_id']): float(row['avg_rating'] or 0)
        for row in reviews.values('review_date', 'seller_id').annotate(avg_rating=Avg('rating'))
    }
    for row in daily_seller_orders_qs:
        row_orders = int(row['order_count'] or 0)
        row_delivered = int(row['delivered_orders'] or 0)
        row_returned = int(row['returned_orders'] or 0)
        row_delivery_rate = (row_delivered / row_orders * 100) if row_orders > 0 else 0
        row_return_ratio = (row_returned / row_orders * 100) if row_orders > 0 else 0
        row_rating = daily_seller_reviews_map.get((row['order_date'], row['seller_id']), 0.0)
        row_norm_rating = (row_rating / 5.0) * 100 if row_rating > 0 else 0
        row_score = (
            row_norm_rating * 0.4 +
            row_delivery_rate * 0.4 +
            (100.0 - row_return_ratio) * 0.2
        ) if row_orders > 0 else 0

        snapshot_list.append({
            'date': row['order_date'],
            'seller': {'pk': row['seller_id'], 'name': row['seller__name']},
            'sales_volume': float(row['sales_volume'] or 0),
            'order_count': row_orders,
            'delivered_sales': float(row['delivered_sales'] or 0),
            'delivered_orders': row_delivered,
            'avg_rating': row_rating,
            'delivery_rate': row_delivery_rate,
            'return_ratio': row_return_ratio,
            'performance_score': row_score
        })

    # ============================================
    # CONTEXT DATA
    # ============================================
    context = {
        'snapshots': snapshot_list,
        'snapshot_count': len(snapshot_list),
        'date_from': date_from_obj.isoformat(),
        'date_to': date_to_obj.isoformat(),
        'seller_filter': seller_filter,
        'total_sales_volume': round(total_sales_volume, 2),
        'avg_performance_score': round(avg_performance_score, 2),
        'avg_delivery_rate': round(avg_delivery_rate, 2),
        'avg_return_ratio': round(avg_return_ratio, 2),
        'daily_sales': mark_safe(json.dumps(daily_sales)),
        'performance_trend': mark_safe(json.dumps(performance_trend)),
        'delivery_trend': mark_safe(json.dumps(delivery_trend)),
        'top_sellers': top_sellers,
        'sellers': Seller.objects.all().order_by('name'),
        'has_snapshots': True,
    }
    
    return render(request, 'reports.html', context)

@login_required
def reports_download(request):
    """Return CSV download of the current reports selection."""
    from django.http import HttpResponse
    import csv

    # parse dates and filters (same defaults)
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if not date_from:
        date_from = (timezone.now().date() - timedelta(days=30)).isoformat()
    if not date_to:
        date_to = timezone.now().date().isoformat()

    try:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        date_from_obj = timezone.now().date() - timedelta(days=30)
        date_to_obj = timezone.now().date()

    seller_filter = request.GET.get('seller', '')
    seller_id = None
    if seller_filter:
        try:
            seller_id = int(seller_filter)
        except ValueError:
            seller_id = None

    orders = Order.objects.filter(
        order_date__gte=date_from_obj,
        order_date__lte=date_to_obj
    )
    reviews = Review.objects.filter(
        review_date__gte=date_from_obj,
        review_date__lte=date_to_obj
    )
    if seller_id:
        orders = orders.filter(seller_id=seller_id)
        reviews = reviews.filter(seller_id=seller_id)

    # Build CSV
    response = HttpResponse(content_type='text/csv')
    filename = f"performance_report_{date_from_obj.isoformat()}_{date_to_obj.isoformat()}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Seller', 'Placed Sales', 'Placed Orders', 'Placed Returns',
        'Delivered Sales', 'Delivered Orders', 'Delivered Returns',
        'Avg Rating', 'Delivery Rate', 'Return Ratio', 'Performance Score'
    ])

    daily_seller_orders_qs = orders.values('order_date', 'seller_id', 'seller__name').annotate(
        sales_volume=Sum('total_amount'),
        order_count=Count('id'),
        placed_returns=Count('id', filter=Q(is_returned=True)),
        delivered_sales=Sum('total_amount', filter=Q(delivery_status='Delivered')),
        delivered_orders=Count('id', filter=Q(delivery_status='Delivered')),
    ).order_by('order_date', 'seller__name')

    daily_seller_reviews_map = {
        (row['review_date'], row['seller_id']): float(row['avg_rating'] or 0)
        for row in reviews.values('review_date', 'seller_id').annotate(avg_rating=Avg('rating'))
    }

    for row in daily_seller_orders_qs:
        row_orders = int(row['order_count'] or 0)
        row_delivered = int(row['delivered_orders'] or 0)
        row_returns = int(row['placed_returns'] or 0)
        row_delivery_rate = (row_delivered / row_orders * 100) if row_orders > 0 else 0
        row_return_ratio = (row_returns / row_orders * 100) if row_orders > 0 else 0
        row_rating = daily_seller_reviews_map.get((row['order_date'], row['seller_id']), 0.0)
        row_norm_rating = (row_rating / 5.0) * 100 if row_rating > 0 else 0
        row_score = (
            row_norm_rating * 0.4 +
            row_delivery_rate * 0.4 +
            (100.0 - row_return_ratio) * 0.2
        ) if row_orders > 0 else 0

        writer.writerow([
            row['order_date'].isoformat(),
            row['seller__name'],
            f"{float(row['sales_volume'] or 0):.2f}",
            row_orders,
            row_returns,
            f"{float(row['delivered_sales'] or 0):.2f}",
            row_delivered,
            row_returns,
            f"{row_rating:.2f}",
            f"{row_delivery_rate:.2f}",
            f"{row_return_ratio:.2f}",
            f"{row_score:.2f}",
        ])

    return response
from django.contrib.auth.models import User
from django.http import HttpResponse

def create_admin(request):
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser(
            username="admin",
            email="admin@gmail.com",
            password="admin123"
        )
        return HttpResponse("Superuser created successfully!")

    return HttpResponse("Superuser already exists.")