from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


# ============================================
# SELLER MODEL
# ============================================
class Seller(models.Model):
    """
    E-Commerce Seller Model
    Represents sellers on the platform with their basic information and status.
    """
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Under Review', 'Under Review'),
        ('Suspended', 'Suspended'),
    ]

    name = models.CharField(max_length=100, help_text="Seller's business name")
    email = models.EmailField(unique=True, help_text="Seller's contact email")
    phone = models.CharField(max_length=15, help_text="Seller's contact phone number")
    address = models.TextField(help_text="Seller's business address")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Active',
        help_text="Current status of the seller account"
    )
    # Using created_at as registration_date (industry standard naming)
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Registration date - when seller joined the platform"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Seller"
        verbose_name_plural = "Sellers"

    def __str__(self):
        return self.name

    @property
    def registration_date(self):
        """Alias for created_at to match specification"""
        return self.created_at.date()


# ============================================
# ORDER MODEL
# ============================================
class Order(models.Model):
    """
    E-Commerce Order Model
    Tracks orders placed through sellers with delivery tracking.
    """
    DELIVERY_STATUS = [
        ('Delivered', 'Delivered'),
        ('Delayed', 'Delayed'),
        ('Failed', 'Failed'),
    ]

    seller = models.ForeignKey(
        Seller,
        on_delete=models.CASCADE,
        related_name='orders',
        help_text="Seller who fulfilled this order"
    )
    order_date = models.DateField(help_text="Date when order was placed")
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Total order value in currency"
    )
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS,
        help_text="Current delivery status"
    )
    is_returned = models.BooleanField(
        default=False,
        help_text="Whether this order was returned by customer"
    )
    

    class Meta:
        ordering = ['-order_date']
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        indexes = [
            models.Index(fields=['-order_date']),
            models.Index(fields=['seller', '-order_date']),
            models.Index(fields=['delivery_status']),
        ]

    def __str__(self):
        return f"Order {self.id} - {self.seller.name}"



# ============================================
# REVIEW MODEL
# ============================================
class Review(models.Model):
    """
    Customer Review Model
    Stores customer feedback and ratings for sellers.
    """
    seller = models.ForeignKey(
        Seller,
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="Seller being reviewed"
    )
    # Optional order reference per specification
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        help_text="Optional reference to the order being reviewed"
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    comment = models.TextField(help_text="Customer review comment")
    review_date = models.DateField(
        auto_now_add=True,
        help_text="Date when review was submitted"
    )

    class Meta:
        ordering = ['-review_date']
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        indexes = [
            models.Index(fields=['-review_date']),
            models.Index(fields=['seller', '-review_date']),
            models.Index(fields=['rating']),
        ]

    def __str__(self):
        return f"{self.seller.name} - {self.rating} Stars"

    @property
    def created_at(self):
        """Alias for review_date to match specification"""
        return self.review_date


# ============================================
# PERFORMANCE MODEL (Current Aggregate)
# ============================================
class Performance(models.Model):
    """
    Current Performance Aggregate Model
    Stores the latest calculated performance metrics for each seller.
    This is a OneToOne relationship - one performance record per seller.
    """
    seller = models.OneToOneField(
        Seller,
        on_delete=models.CASCADE,
        related_name='performance',
        help_text="Seller this performance data belongs to"
    )
    total_orders = models.IntegerField(
        default=0,
        help_text="Total number of orders"
    )
    average_rating = models.FloatField(
        default=0.0,
        help_text="Average customer rating (1-5 scale)"
    )
    delivery_rate = models.FloatField(
        default=0.0,
        help_text="Percentage of successfully delivered orders"
    )
    return_rate = models.FloatField(
        default=0.0,
        help_text="Percentage of returned orders"
    )
    performance_score = models.FloatField(
        default=0.0,
        help_text="Calculated performance score (weighted composite)"
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="Last time performance metrics were calculated"
    )

    class Meta:
        ordering = ['-performance_score']
        verbose_name = "Performance"
        verbose_name_plural = "Performances"

    def __str__(self):
        return f"Performance - {self.seller.name}"


# ============================================
# PERFORMANCE SNAPSHOT MODEL (Historical)
# ============================================
class PerformanceSnapshot(models.Model):
    """
    Historical Performance Snapshot Model
    Stores time-series performance data for trend analysis and reporting.
    One seller can have multiple snapshots (one per day/week/month).
    """
    seller = models.ForeignKey(
        Seller,
        on_delete=models.CASCADE,
        related_name='snapshots',
        help_text="Seller this snapshot belongs to"
    )
    date = models.DateField(
        help_text="Date of this performance snapshot"
    )
    sales_volume = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total sales volume for this period"
    )
    order_count = models.IntegerField(
        default=0,
        help_text="Number of orders in this period"
    )
    avg_rating = models.FloatField(
        default=0.0,
        help_text="Average rating for this period"
    )
    delivery_rate = models.FloatField(
        default=0.0,
        help_text="Delivery success rate for this period"
    )
    return_ratio = models.FloatField(
        default=0.0,
        help_text="Return ratio for this period"
    )
    delivered_sales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total value of delivered orders for this period"
    )
    delivered_orders = models.IntegerField(
        default=0,
        help_text="Number of delivered orders in this period"
    )
    performance_score = models.FloatField(
        default=0.0,
        help_text="Performance score for this period"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this snapshot was created"
    )

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Performance Snapshot"
        verbose_name_plural = "Performance Snapshots"
        unique_together = [['seller', 'date']]  # One snapshot per seller per day
        indexes = [
            models.Index(fields=['-date']),
            models.Index(fields=['seller', '-date']),
            models.Index(fields=['-performance_score']),
        ]

    def __str__(self):
        return f"Snapshot - {self.seller.name} - {self.date}"


