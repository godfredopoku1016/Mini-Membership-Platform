from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from PIL import Image
import uuid

class MembershipPlan(models.Model):
    """Represents different membership tiers"""
    TIER_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
    ]
    
    name = models.CharField(max_length=100)
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField()
    max_members = models.PositiveIntegerField(default=50)
    features = models.TextField(help_text="List one feature per line")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(blank=True,null=True,auto_now_add=True)
    updated_at = models.DateTimeField(blank=True,null=True,auto_now=True)

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f"{self.tier.title()} - ${self.price}/month"

    def get_features_list(self):
        return self.features.split("\n")

class UserMembership(models.Model):
    """Links users to their membership plans"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.ForeignKey(MembershipPlan, on_delete=models.SET_NULL, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    current_period_start = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(blank=True,null=True,auto_now_add=True)
    updated_at = models.DateTimeField(blank=True,null=True,auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.plan.tier if self.plan else 'No Plan'}"

    @property
    def is_active(self):
        return self.status == 'active'

class Payment(models.Model):
    """Stores payment history"""
    CURRENCY_CHOICES = [
        ('USD', 'USD ($)'),
        ('EUR', 'EUR (€)'),
        ('GBP', 'GBP (£)'),
    ]
    
    STATUS_CHOICES = [
        ('succeeded', 'Succeeded'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,blank=True,null=True)
    user_membership = models.ForeignKey(UserMembership, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(default=100,max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    stripe_payment_intent_id = models.CharField(default='pending_creation',max_length=100, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(blank=True,null=True,auto_now_add=True)
    updated_at = models.DateTimeField(blank=True,null=True,auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.stripe_payment_intent_id} - {self.amount} {self.currency}"

class UserProfile(models.Model):
    """Extended user profile information"""
    USER_TYPE_CHOICES = [
        ('member', 'Member'),
        ('admin', 'Administrator'),
        ('staff', 'Staff'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='member')
    fname = models.CharField(max_length=50,blank=True,null=True)
    lname = models.CharField(max_length=50,blank=True,null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True,null=True)
    address = models.TextField(blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        default='profile_pictures/default.png'
    )
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(blank=True,null=True,auto_now_add=True)
    updated_at = models.DateTimeField(blank=True,null=True,auto_now=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.username} - {self.user_type}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Resize profile picture if it exists
        if self.profile_picture:
            try:
                img = Image.open(self.profile_picture.path)
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.profile_picture.path)
            except:
                # Handle cases where image might not exist or is corrupted
                pass

    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip()

    @property
    def is_member(self):
        return self.user_type == 'member'

    @property
    def is_admin(self):
        return self.user_type == 'admin'

    @property
    def is_staff(self):
        return self.user_type == 'staff'

class Member(models.Model):
    """Additional member-specific information"""
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    membership = models.ForeignKey(UserMembership, on_delete=models.SET_NULL, null=True, blank=True)
    join_date = models.DateTimeField(auto_now_add=True)
    renewal_date = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-join_date']

    def __str__(self):
        return f"Member: {self.user_profile.user.username}"

class ActivityLog(models.Model):
    """Tracks user activities"""
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('payment', 'Payment'),
        ('profile_update', 'Profile Update'),
        ('membership_change', 'Membership Change'),
        ('password_reset', 'Password Reset'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"

class Notification(models.Model):
    """System notifications for users"""
    TYPE_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('error', 'Error'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='info')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    link = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True,null=True,auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.title}"

class SystemSetting(models.Model):
    """Global system settings"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(blank=True,null=True,auto_now_add=True)
    updated_at = models.DateTimeField(blank=True,null=True,auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return self.key
