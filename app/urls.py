from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import login_view, admin_dashboard, logout_view, custom_admin_view, signup_view, verify_email
from . import views
from .views import home, signup
from django.conf import settings




urlpatterns = [
    path("", views.index, name="index"),
    path('home/', home, name='home'),           # ← Root URL
    path('signup/', signup, name='signup'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path("branding/", views.branding, name="branding"),
    path("social/", views.social, name="social"),
    path("clothing/", views.clothing, name="clothing"),
    path("shop/", views.shop, name="shop"),
    path("list/", views.list, name="list"),
    

# Buy Now (Direct Payment)
    path('buy-now/<int:product_id>/', views.buy_now, name='buy_now'),
    
    path('checkout/<int:product_id>/', views.checkout, name='checkout'),
    path('payment/verify/', views.verify_payment, name='verify_payment'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('webhook/paystack/', views.paystack_webhook, name='paystack_webhook'),

    


    # ================= admin dashboard ==========
    path('contact/', views.contact_admin, name='contact'),
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
    path('dashboard/users/', views.admin_users, name='admin_users'),
    path('dashboard/messages/', views.admin_messages, name='admin_messages'),
    path('dashboard/product/delete/<int:pk>/', views.delete_product, name='delete_product'),
]