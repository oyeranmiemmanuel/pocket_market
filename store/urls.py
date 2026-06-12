from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
# from .views import login_view, admin_dashboard, logout_view, custom_admin_view, signup_view, verify_email
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", views.index, name="index"),
    path('home/', views.home, name='home'),           # ← Root URL
    path('signup/', views.signup, name='signup'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path("branding/", views.branding, name="branding"),
    path("social/", views.social, name="social"),
    path("flyer/", views.flyer, name="flyer"),
    path("clothing/", views.clothing, name="clothing"),
    path("portfolio/", views.portfolio, name="portfolio"),
    path("shop/", views.shop, name="shop"),
    path('contact/', views.contact_admin, name='contact'),
]