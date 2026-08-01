from django.urls import path
from .views import login_view, admin_dashboard, logout_view, custom_admin_view, signup_view, verify_email
from . import views
from .views import home
from django.conf import settings




urlpatterns = [
    path("", views.index, name="index"),
    path('home/', home, name='home'),           # ← Root URL
    path("branding/", views.branding, name="branding"),
    path("social/", views.social, name="social"),
    path("clothing/", views.clothing, name="clothing"),
    # 'shop' moved to apps.catalog (product_list/product_detail) - see
    # config/urls.py. Old buy_now/checkout/download_product/verify_payment/
    # payment_success/paystack_webhook retired - see docs/28_DECISIONS.md.

    # ================= admin dashboard ==========
    path('contact/', views.contact_admin, name='contact'),
    path('password-verify/', views.password_verify, name='password_verify'),
    path('custom_login/', login_view, name='custom_login'),
    path('custom_signup/', signup_view, name='custom_signup'),
    path('base/', custom_admin_view, name='custom_admin'),
    path('admin-panel/', admin_dashboard, name='admin_dashboard'),
    path('custom_logout/', logout_view, name='custom_logout'),
    path(
        'verify-email/<uidb64>/<token>/',
        verify_email,
        name='verify_email'
    ),


    
    path('dashboard/orders/', views.admin_orders, name='admin_orders'),
    path('dashboard/products/', views.admin_products, name='admin_products'),
    path('admin-panel/products/add/', views.add_product, name='add_product'),
    path('admin-panel/products/edit/<uuid:pk>/', views.edit_product, name='edit_product'),
    path('dashboard/users/', views.admin_users, name='admin_users'),
    path('dashboard/messages/', views.admin_messages, name='admin_messages'),
    path('dashboard/product/delete/<uuid:pk>/', views.delete_product, name='delete_product'),
]