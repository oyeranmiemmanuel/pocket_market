from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .forms import PasswordVerificationForm, ProductForm
from .models import ContactMessage
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.decorators import login_required, user_passes_test
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.db import models
from django.shortcuts import render
from django.conf import settings
from .models import Order, ContactMessage
from apps.catalog.models import Product
from .forms import MessageForm

User = get_user_model()

import uuid
import requests
import json
import hmac
import hashlib
from django.views.decorators.csrf import csrf_exempt

user = settings.AUTH_USER_MODEL

class OrderAdminHelper:
    """Helper class for custom admin order functions"""

    @staticmethod
    def amount_display(obj):
        return f"₦{obj.amount:,}"
    amount_display.short_description = "Amount"

    @staticmethod
    def purchase_status(obj):
        if getattr(obj, 'verified', False) and not getattr(obj, 'purchase_completed', False):
            return "⚠ Recovery Needed"
        return "✅ Completed"
    purchase_status.short_description = "Purchase Status"

    @staticmethod
    def mark_as_verified(queryset):
        queryset.update(verified=True, status='paid')

    @staticmethod
    def recover_failed_purchase(queryset):
        recovered = 0
        for order in queryset:
            if order.verified and not getattr(order, 'purchase_completed', False):
                order.purchase_completed = True
                order.status = 'completed'
                order.save()
                recovered += 1
        return recovered



# 404 NOT FOUND
def custom_404(request, exception):
    return render(request, '404.html', status=404)

# ====================== AUTHENTICATION ======================

def home(request):
    # If user is not logged in, send them to signup
    if not request.user.is_authenticated:
        return redirect('accounts:register')

    return render(request, 'core/base.html')



@login_required
def password_verify(request):
    """Simple password verification page (e.g., before sensitive actions)"""
    if request.method == 'POST':
        form = PasswordVerificationForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data.get('password')
            if request.user.check_password(password):
                messages.success(request, "Password verified successfully!")
                return redirect('home')  # Or wherever you want to go after verification
            else:
                messages.error(request, "Incorrect password.")
    else:
        form = PasswordVerificationForm()
    return render(request, 'password_verify.html', {'form': form})

# def home(request):
#     return render(request, 'home')




def index(request):
    return render(request, "core/base.html", {})




# ====================== ADMIN DASHBOARD ======================



# Check if user is staff or superuser
def is_admin(user):
    return user.is_staff or user.is_superuser



def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.is_staff = True
            user.save()

            send_verification_email(request, user)
            messages.success(request, "Account created! Please check your email to verify.")
            return redirect('custom_login')
    else:
        form = UserCreationForm()

    return render(request, 'custom_admin/custom_signup.html', {'form': form})



def send_verification_email(request, user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    verification_link = request.build_absolute_uri(
        reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
    )

    subject = "Verify Your Admin Account"
    message = render_to_string('custom_admin/email_verification.html', {
        'user': user,
        'verification_link': verification_link,
    })

    send_mail(subject, message, None, [user.email], fail_silently=False)




def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Email verified successfully! You can now login.")
        return redirect('custom_login')
    else:
        messages.error(request, "Verification link is invalid or has expired.")
        return redirect('custom_signup')




# =========================
# LOGIN VIEW
# =========================
def login_view(request):

    if request.user.is_authenticated:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            if user.is_staff or user.is_superuser:
                login(request, user)
                return redirect('admin_dashboard')

            else:
                messages.error(
                    request,
                    'You do not have permission to access this dashboard.'
                )

        else:
            messages.error(
                request,
                'Invalid username or password.'
            )

    return render(
        request,
        'custom_admin/custom_login.html'
    )

# =========================
# ADMIN DASHBOARD
# =========================

@login_required
@user_passes_test(is_admin)
def custom_admin_view(request):

    return redirect('admin_dashboard')


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):

    total_users = User.objects.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_messages = ContactMessage.objects.count()

    revenue = Order.objects.filter(
        verified=True,
        status='paid'
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    

    failed_purchases = Order.objects.filter(
    verified=True,
    purchase_completed=False
).count()
    
    recent_orders = Order.objects.order_by('-created_at')[:10]
    recent_products = Product.objects.order_by('-created_at')[:10]
    recent_messages = ContactMessage.objects.order_by('-created_at')[:10]

    context = {
        'title': 'Admin Dashboard',
        'total_users': total_users,
        'total_products': total_products,
        'total_orders': total_orders,
        'failed_purchases': failed_purchases,
        'total_messages': total_messages,
        'revenue': revenue,
        'recent_orders': recent_orders,
        'recent_products': recent_products,
        'recent_messages': recent_messages,
    }
    
    return render(
        request,
        'custom_admin/dashboard.html',
        context
        
    )


@login_required
@user_passes_test(is_admin)
def admin_orders(request):
    orders = Order.objects.all().order_by('-created_at')

    # Add custom methods as context
    for order in orders:
        order.amount_display = f"₦{order.amount:,}"
        if order.verified and not getattr(order, 'purchase_completed', False):
            order.purchase_status = "⚠ Recovery Needed"
        else:
            order.purchase_status = "✅ Completed"

    context = {
        'orders': orders,
        'title': 'Manage Orders',
        'OrderAdminHelper': OrderAdminHelper,
    }

    return render(request, 'custom_admin/orders.html', context)

@login_required
@user_passes_test(is_admin)
def admin_products(request):
    products = Product.objects.all()

    return render(
        request,
        'custom_admin/products.html',
        {'products': products}
    )

@login_required
@user_passes_test(is_admin)
def delete_product(request, pk):

    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        product.delete()

        messages.success(
            request,
            "Product deleted successfully."
        )

        return redirect('admin_products')

    return render(
        request,
        'custom_admin/delete_product.html',
        {
            'product': product
        }
    )



@login_required
@user_passes_test(is_admin)
def add_product(request):

    if request.method == 'POST':
        form = ProductForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Product added successfully."
            )

            return redirect('admin_products')

    else:
        form = ProductForm()

    return render(
        request,
        'custom_admin/add_product.html',
        {
            'form': form
        }
    )


@login_required
@user_passes_test(is_admin)
def edit_product(request, pk):

    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductForm(
            request.POST,
            request.FILES,
            instance=product,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Product updated successfully."
            )

            return redirect('admin_products')

    else:
        form = ProductForm(instance=product)

    return render(
        request,
        'custom_admin/edit_product.html',
        {
            'form': form,
            'product': product,
        }
    )






@login_required
@user_passes_test(is_admin)
def admin_users(request):
    users = User.objects.all()

    return render(
        request,
        'custom_admin/users.html',
        {'users': users}
    )


@login_required
@user_passes_test(is_admin)
def admin_messages(request):
    messages_list = ContactMessage.objects.all().order_by('-created_at')

    return render(
        request,
        'custom_admin/messages.html',
        {'messages_list': messages_list}
    )




    


# =========================
# LOGOUT VIEW
# =========================
def logout_view(request):
    logout(request)
    return render(request, 'custom_admin/custom_logout.html')

def admin_panel(request):
    if not request.user.is_authenticated:
        return redirect('custom_login')

    return render(request, 'custom_admin/dashboard.html',)




# ====================== SHOP & PAYMENT ======================
# Retired: the old single-product buy_now/checkout/verify_payment/
# download_product/paystack_webhook flow. Superseded by the cart-based
# checkout in apps.orders/apps.payments/apps.delivery - see
# docs/28_DECISIONS.md. Product browsing now lives in apps.catalog
# (product_list/product_detail), not here.

# ====================== OTHER PAGES ======================

def branding(request):
    return render(request, "services/branding.html", {})


def social(request):
    return render(request, "services/social.html", {})


# def flyer(request):
#     return render(request, "main/flyer.html", {})


def clothing(request):
    return render(request, "products/clothing.html", {})



def contact_admin(request):
    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message_text = request.POST.get('message', '').strip()

        # Validation
        if len(name) < 3:
            messages.error(request, "Name must be at least 3 characters.")
            return render(request, 'main/contact.html', {})

        if len(message_text) < 20:
            messages.error(request, "Message must be at least 20 characters.")
            return render(request, 'main/contact.html', {})

        try:
            # Save message to database
            contact_msg = ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message_text
            )

            # Send Email Notification to Admin
            admin_email = 'nicholasereh@gmail.com'

            send_mail(
                subject=f"New Contact Message: {subject}",
                message=f"""
You have received a new message from your website!

Name: {name}
Email: {email}
Subject: {subject}

Message:
{message_text}

View in Admin Panel: http://127.0.0.1:8000/dashboard/
                """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_email],
                fail_silently=False,
            )

            messages.success(request, "✅ Your message has been sent successfully! Nicholas will reply soon.")
            return redirect('contact')

        except Exception as e:
            messages.error(request, "Failed to send message. Please try again later.")

    return render(request, 'main/contact.html', {})



