from django.db import models
from django.contrib.auth.models import User
# Create your models here.


class ToDolist(models.Model):
    name = models.CharField(max_length=200)

    def str(self):
        return self.name 

class Item(models.Model):
    ToDolist = models.ForeignKey(ToDolist, on_delete=models.CASCADE)
    text = models.CharField(max_length=300)
    complete = models.BooleanField()

def str(self):
    return self.text


class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    date_sent = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.subject}"
    



class UserProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    other_names = models.CharField(
        max_length=200
    )

    date_of_birth = models.DateField()

    phone = models.CharField(
        max_length=20
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.user.username
    

    


class Product(models.Model):
    PRODUCT_TYPES = (
        ('digital', 'Digital Product'),
        ('physical', 'Physical Product'),
    )

    name = models.CharField(max_length=200)
    description = models.TextField()

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True
    )

    product_type = models.CharField(
        max_length=10,
        choices=PRODUCT_TYPES,
        default='physical'
    )

    digital_file = models.FileField(
        upload_to='digital_products/',
        blank=True,
        null=True
    )

    stock = models.PositiveIntegerField(
        default=0,
        help_text="Number of items available"
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.name

    @property
    def is_digital(self):
        return self.product_type == 'digital'
    

    
class Order(models.Model):
    """Model to store customer orders and payment information"""
    
    # Customer Information
    user = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='orders'
    )
    email = models.EmailField()
    full_name = models.CharField(max_length=150, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Payment Information
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # in Naira
    reference = models.CharField(max_length=100, unique=True)
    paystack_reference = models.CharField(max_length=100, blank=True, null=True)
    purchase_completed = models.BooleanField(default=False)
    
    # Order Status
    verified = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.reference} - {self.email} - ₦{self.amount}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Order"
        verbose_name_plural = "Orders"