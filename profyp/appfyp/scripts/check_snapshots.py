import os
import django
from datetime import date, timedelta
from django.db.models import Sum

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'profyp.settings')
django.setup()

from appfyp.models import Order, PerformanceSnapshot, Seller

start = date.today() - timedelta(days=30)
end = date.today()

print(f"Checking orders (by order_date) vs snapshots for {start} -> {end}")

orders = Order.objects.filter(order_date__range=(start, end))
print('Orders in range:', orders.count())

snap_orders_total = PerformanceSnapshot.objects.filter(date__range=(start, end)).aggregate(total_orders=Sum('order_count'))
print('Total order_count in snapshots:', snap_orders_total.get('total_orders'))

# Find orders that do not have a matching snapshot (by seller and order_date)
missing = []
for o in orders.select_related('seller'):
    exists = PerformanceSnapshot.objects.filter(seller=o.seller, date=o.order_date).exists()
    if not exists:
        missing.append((o.id, o.seller.id, str(o.order_date)))

print('Orders missing snapshots (sample up to 20):', len(missing))
for row in missing[:20]:
    print('order_id', row[0], 'seller_id', row[1], 'date', row[2])

# Per-seller discrepancies (orders vs snapshot totals)
from django.db.models import Count

orders_by_seller = orders.values('seller').annotate(ord_count=Count('id'))
for entry in orders_by_seller:
    seller_id = entry['seller']
    ord_count = entry['ord_count']
    snap_total = PerformanceSnapshot.objects.filter(seller_id=seller_id, date__range=(start, end)).aggregate(total=Sum('order_count'))['total'] or 0
    if ord_count != snap_total:
        s = Seller.objects.get(pk=seller_id)
        print(f"Seller {s.id} ({s.name}): orders={ord_count}, snapshot_orders={snap_total}")

print('Done')
