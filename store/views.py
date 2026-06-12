# views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import SignupForm, LoginForm, PasswordVerificationForm

def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)

        if form.is_valid():
            user = form.save()

            # Log the user in automatically
            login(request, user)

            messages.success(
                request,
                "Signup successful! Welcome."
            )

            # Redirect to home page
            return redirect('home')

    else:
        form = SignupForm()

    return render(
        request,
        'main/signup.html',
        {'form': form}
    )

# if user.is_staff or user.is_superuser:
#     return redirect('admin_dashboard')
# else:
#     return redirect('home')

def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, "Login successful!")
                return redirect('home')
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()
    return render(request, 'main/login.html', {'form': form})

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

def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


# def home(request):
#     return render(request, 'home')




def index(request):
    return render(request, "main/base.html", {})


def home(request):
    return render(request, "main/home.html", {})


# ====================== SHOP & PAYMENT ======================
def shop(request):
    products = Product.objects.all()
    return render(request, 'main/shop.html', {'products': products})

# ====================== OTHER PAGES ======================

def branding(request):
    return render(request, "main/branding.html", {})


def social(request):
    return render(request, "main/social.html", {})


def flyer(request):
    return render(request, "main/flyer.html", {})


def clothing(request):
    return render(request, "main/clothing.html", {})


def portfolio(request):
    return render(request, "main/portfolio.html", {})

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

View in Admin Panel: http://127.0.0.1:8000/admin/
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



