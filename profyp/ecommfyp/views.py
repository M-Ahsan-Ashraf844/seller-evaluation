from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from appfyp.models import Seller, Order, Review
from appfyp.performance_utils import calculate_performance
from .models import Product


def home(request):
	products = Product.objects.select_related('seller').all().order_by('-created_at')
	return render(request, 'home.html', {'products': products})


def product_detail(request, pk):
	product = get_object_or_404(Product, pk=pk)
	# show seller reviews on product page
	reviews = product.seller.reviews.all().order_by('-review_date')[:20]
	return render(request, 'product_detail.html', {'product': product, 'reviews': reviews})


def add_to_cart(request, pk):
	product = get_object_or_404(Product, pk=pk)
	# support both POST (form) and GET (?qty=) for convenience
	if request.method == 'POST':
		try:
			qty = int(request.POST.get('qty', 1))
		except (ValueError, TypeError):
			qty = 1
	else:
		try:
			qty = int(request.GET.get('qty', 1))
		except (ValueError, TypeError):
			qty = 1

	cart = request.session.get('cart', {})
	# cart structure: {product_id: {'qty': int}}
	item = cart.get(str(product.id), {'qty': 0})
	item['qty'] = item.get('qty', 0) + max(1, qty)
	cart[str(product.id)] = item
	request.session['cart'] = cart

	# Redirect back to product or cart depending on source
	next_url = request.POST.get('next') or request.GET.get('next')
	if next_url:
		return redirect(next_url)
	return redirect('ecomm_cart')


@login_required
def add_review(request, pk):
	product = get_object_or_404(Product, pk=pk)
	if request.method != 'POST':
		return redirect('ecomm_product_detail', pk=pk)

	# Parse rating and comment
	try:
		rating = int(request.POST.get('rating', 0))
	except (ValueError, TypeError):
		rating = 0
	comment = request.POST.get('comment', '').strip()

	if rating < 1 or rating > 5 or not comment:
		# simple validation: require rating 1-5 and non-empty comment
		return redirect('ecomm_product_detail', pk=pk)

	# Create Review in appfyp.models; order link is optional so leave None
	Review.objects.create(
		seller=product.seller,
		order=None,
		rating=rating,
		comment=comment
	)

	# Recalculate performance for seller
	try:
		calculate_performance(product.seller)
	except Exception:
		pass

	return redirect('ecomm_product_detail', pk=pk)


def cart_view(request):
	cart = request.session.get('cart', {})
	items = []
	total = 0
	for pid, data in cart.items():
		try:
			prod = Product.objects.select_related('seller').get(pk=int(pid))
		except Product.DoesNotExist:
			continue
		qty = int(data.get('qty', 1))
		line_total = float(prod.price) * qty
		total += line_total
		items.append({'product': prod, 'qty': qty, 'line_total': line_total})
	return render(request, 'cart.html', {'items': items, 'total': round(total, 2)})


def checkout(request):
	cart = request.session.get('cart', {})
	if not cart:
		return redirect('ecomm_cart')

	# Group cart items by seller and create one Order per seller
	sellers_map = {}
	for pid, data in cart.items():
		try:
			prod = Product.objects.select_related('seller').get(pk=int(pid))
		except Product.DoesNotExist:
			continue
		sid = prod.seller_id
		qty = int(data.get('qty', 1))
		sellers_map.setdefault(sid, {'seller': prod.seller, 'total': 0.0})
		sellers_map[sid]['total'] += float(prod.price) * qty

	created_orders = []
	today = timezone.now().date()
	for sid, vals in sellers_map.items():
		seller = vals['seller']
		total_amount = round(vals['total'], 2)
		order = Order.objects.create(
			seller=seller,
			order_date=today,
			total_amount=total_amount,
			delivery_status='Delivered',
			is_returned=False
		)
		created_orders.append(order)
		# Update performance immediately
		try:
			calculate_performance(seller)
		except Exception:
			pass

	# Clear cart
	request.session['cart'] = {}

	# Redirect to a simple confirmation page showing created orders and seller evaluations
	return render(request, 'checkout_success.html', {'orders': created_orders})
