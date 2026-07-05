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
from .models import Order, Product, ContactMessage
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
    recent_messages = ContactMessage.objects.order_by('-date_sent')[:10]

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
    messages_list = ContactMessage.objects.all().order_by('-date_sent')

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
def shop(request):
    products = Product.objects.filter(is_active=True)

    return render(request, 'services/shop.html', {'products': products})


def checkout(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == "POST":
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()

        if not full_name or not email:
            messages.error(request, "Full Name and Email are required.")
            return render(request, 'payment/checkout.html', {'product': product})

        amount_in_kobo = int(product.price * 100)
        reference = str(uuid.uuid4())

        try:
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                full_name=full_name,
                email=email,
                phone=phone,
                amount=product.price,
                reference=reference,
            )

            url = "https://api.paystack.co/transaction/initialize"
            headers = {
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            }
            data = {
                "email": email,
                "amount": amount_in_kobo,
                "reference": reference,
                "callback_url": "http://toptech.pythonanywhere.com/payment/verify/",
                "metadata": {
                    "product_id": product.id,
                    "product_name": product.name,
                    "is_digital": product.is_digital
                }
            }

            response = requests.post(url, json=data, headers=headers, timeout=10)
            res_data = response.json()

            if res_data.get('status') is True:
                return redirect(res_data['data']['authorization_url'])
            else:
                messages.error(request, f"Paystack Error: {res_data.get('message', 'Unknown error')}")
                print("Paystack Response:", res_data)

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            print("Checkout Exception:", str(e))

        return redirect('checkout', product_id=product_id)

    return render(request, 'payment/checkout.html', {'product': product})


def verify_payment(request):
    reference = request.GET.get('reference')

    if not reference:
        messages.error(request, "No payment reference found.")
        return redirect('shop')

    try:
        # Verify with Paystack
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}

        response = requests.get(url, headers=headers)
        res_data = response.json()

        if res_data.get('status') and res_data['data']['status'] == 'success':
            order = Order.objects.get(reference=reference)
            order.verified = True
            order.status = 'paid'
            # Product not yet delivered
            order.purchase_completed = False
            order.save()


            # When download access, product activation, or order fulfillment succeeds:

            order.purchase_completed = True
            order.status = 'completed'
            order.save()


            product_id = res_data['data'].get('metadata', {}).get('product_id')

            if product_id:
                product = Product.objects.get(id=product_id)

                if product.is_digital and product.digital_file:
                    # Digital Product → Auto Download
                    return redirect('download_product', product_id=product.id)
                else:
                    # Physical Product → Show Success Message
                    return render(request, 'payment/payment_success_physical.html', {
                        'order': order,
                        'product': product
                    })

            messages.success(request, "Payment successful!")
            return redirect('shop')

        else:
            messages.error(request, "Payment verification failed.")
            return redirect('shop')

    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('shop')    


def payment_success(request):
    return render(request, 'payment/payment_success.html')
    

@csrf_exempt



def download_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if not product.is_digital or not product.digital_file:
        messages.error(request, "This product is not available for download.")
        return redirect('shop')

    response = HttpResponse(product.digital_file, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{product.digital_file.name.split("/")[-1]}"'
    
    return response



def paystack_webhook(request):
    """Secure webhook to verify payments from Paystack"""
    
    # Get Paystack signature from header
    paystack_signature = request.headers.get('x-paystack-signature')
    
    if not paystack_signature:
        return HttpResponse(status=400)

    # Get raw body
    body = request.body
    
    # Verify signature (Security)
    secret = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
    computed_signature = hmac.new(secret, body, hashlib.sha512).hexdigest()

    if not hmac.compare_digest(paystack_signature, computed_signature):
        return HttpResponse(status=401)  # Invalid signature

    # Process the event
    try:
        event = json.loads(body)
        event_type = event.get('event')

        if event_type == 'charge.success':
            reference = event['data']['reference']
            
            try:
                order = Order.objects.get(reference=reference)
                order.verified = True
                order.status = 'paid'
                order.save()

                print(f"✅ Payment confirmed via webhook for Order: {reference}")
                
            except Order.DoesNotExist:
                print(f"⚠️ Order not found: {reference}")

        return HttpResponse(status=200)

    except Exception as e:
        print("Webhook Error:", str(e))
        return HttpResponse(status=400)


def buy_now(request, product_id):
    pass 
    """Direct Buy Now - Initialize Payment for single product"""
    product = get_object_or_404(Product, id=product_id)

    amount = int(product.price * 100)  # Paystack uses kobo
    reference = str(uuid.uuid4())

    order = Order.objects.create(
        email=request.user.email if request.user.is_authenticated else "guest@toptech.com",
        amount=amount,
        reference=reference
    )

    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "email": order.email,
        "amount": amount,
        "reference": reference,
        "callback_url": "http://toptech.pythonanywhere.com/payment/verify/",
    }

    response = requests.post(url, json=data, headers=headers)
    res_data = response.json()

    if res_data.get("status"):
        return redirect(res_data["data"]["authorization_url"])
        
    else:
        messages.error(request, "Payment initialization failed.")
        return redirect('shop')

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
            admin_email = 'nicholasereh@gmailcom'   # ← Change this to your real email

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



