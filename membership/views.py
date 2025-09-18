from datetime import timezone
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db.models import Q
from django.db import transaction
import stripe
import random
from decimal import Decimal
import uuid
from datetime import datetime
from .forms import (
    UserRegistrationForm, UserProfileForm, MembershipUpgradeForm,
    PaymentForm, ContactForm, PasswordResetForm, ConfirmCodeForm, NewPasswordForm
)
from .models import (
    CertificationProgram, IndustryEvent, MemberDirectory, MembershipPlan, UserMembership, Payment, UserProfile,
    ActivityLog, Notification, SystemSetting, User
)

# Stripe API Key
stripe.api_key = settings.STRIPE_SECRET_KEY

# ========================================================
# Utility Functions
# ========================================================

def generate_confirmation_code():
    return str(random.randint(100000, 999999))

def send_confirmation_email(subject, to_email, context, template_name):
    html_message = render_to_string(template_name, context)
    plain_message = strip_tags(html_message)
    
    email = EmailMultiAlternatives(
        subject, 
        plain_message, 
        from_email=settings.DEFAULT_FROM_EMAIL, 
        to=[to_email]
    )
    email.attach_alternative(html_message, 'text/html')
    email.send()

def is_member(user):
    return user.is_authenticated and hasattr(user, 'userprofile') and user.userprofile.user_type == 'member'

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or (hasattr(user, 'userprofile') and user.userprofile.user_type == 'admin'))

def is_staff(user):
    return user.is_authenticated and (user.is_staff or (hasattr(user, 'userprofile') and user.userprofile.user_type == 'staff'))

def log_activity(user, action, description, ip_address=None, user_agent=None):
    """Helper function to log user activities"""
    ActivityLog.objects.create(
        user=user,
        action=action,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent
    )

# ========================================================
# Public Views (No Login Required)
# ========================================================

def homepage(request):
    """Homepage with featured membership plans"""
    featured_plans = MembershipPlan.objects.filter(is_active=True).order_by('price')[:3]
    
    context = {
        'featured_plans': featured_plans,
    }
    return render(request, 'homepage.html', context)

def pricing(request):
    """Display all available membership plans"""
    membership_plans = MembershipPlan.objects.filter(is_active=True).order_by('price')
    
    context = {
        'membership_plans': membership_plans,
    }
    return render(request, 'pricing.html', context)

def about(request):
    """About page"""
    return render(request, 'aboutus.html')

def contact(request):
    """Contact form page"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Process contact form (you can integrate with email service here)
            messages.success(request, 'Thank you for your message! We will get back to you soon.')
            return redirect('homepage')
    else:
        form = ContactForm()
    
    return render(request, 'contact.html', {'form': form})

def login_view(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Log the login activity
            log_activity(
                user, 
                'login', 
                f'User logged in successfully',
                request.META.get('REMOTE_ADDR'),
                request.META.get('HTTP_USER_AGENT')
            )
            
            login(request, user)
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'login.html')

def register_view(request):
    """User registration"""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    
                    # Create UserProfile
                    UserProfile.objects.create(
                        user=user,
                        user_type='member',
                        email=user.email,
                        fname=user.first_name,
                        lname=user.last_name,
                    )
                    
                    # Assign free membership by default
                    free_plan = MembershipPlan.objects.filter(tier='free', is_active=True).first()
                    if free_plan:
                        UserMembership.objects.create(
                                                                                                                                                                                          user=user,
                            plan=free_plan,
                            status='active'
                        )
                    else:
                        # Log warning but don't prevent registration
                        print("Warning: Free membership plan not found. User registered without membership.")
                    
                    # Log registration activity
                    log_activity(
                        user, 
                        'signup', 
                        f'New member registration: {user.username}',
                        request.META.get('REMOTE_ADDR')
                    )
                    
                    # Auto-login the user
                    login(request, user)
                    messages.success(request, 'Registration successful! Welcome to our platform.')
                    return redirect('dashboard')
                    
            except Exception as e:
                # More specific error message for debugging
                error_message = f'Registration failed: {str(e)}'
                print(error_message)  # For debugging in console
                messages.error(request, 'Registration failed. Please try again or contact support.')
        else:
            # More detailed form error display
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = UserRegistrationForm()
    
    return render(request, 'register.html', {'form': form})

def forgot_password_view(request):
    """Password reset request"""
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                confirmation_code = generate_confirmation_code()
                
                # Store in session
                request.session['reset_email'] = user.email
                request.session['confirmation_code'] = confirmation_code
                request.session.set_expiry(300)  # 5 minutes expiration
                
                # Send email
                context = {
                    'username': user.username,
                    'confirmation_code': confirmation_code,
                }
                
                send_confirmation_email(
                    'Password Reset Confirmation Code',
                    user.email,
                    context,
                    'forgot_password_email.html'
                )
                
                messages.success(request, 'Confirmation code sent to your email.')
                return redirect('confirm_code')
                
            except User.DoesNotExist:
                messages.error(request, 'No account found with this email address.')
    else:
        form = PasswordResetForm()
    
    return render(request, 'forgot_password.html', {'form': form})

def confirm_code_view(request):
    """Confirm password reset code"""
    if 'reset_email' not in request.session:
        messages.error(request, 'Session expired. Please try again.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        form = ConfirmCodeForm(request.POST)
        if form.is_valid():
            entered_code = form.cleaned_data['confirmation_code']
            stored_code = request.session.get('confirmation_code')
            
            if entered_code == stored_code:
                return redirect('reset_password')
            else:
                messages.error(request, 'Invalid confirmation code.')
    else:
        form = ConfirmCodeForm()
    
    return render(request, 'confirm_code.html', {'form': form})

def reset_password_view(request):
    """Set new password"""
    if 'reset_email' not in request.session:
        messages.error(request, 'Session expired.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        form = NewPasswordForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.get(email=request.session['reset_email'])
                user.set_password(form.cleaned_data['new_password'])
                user.save()
                
                # Clear session
                del request.session['reset_email']
                del request.session['confirmation_code']
                
                # Log password reset
                log_activity(
                    user, 
                    'password_reset', 
                    'Password reset successfully'
                )
                
                messages.success(request, 'Password reset successfully. Please login.')
                return redirect('login')
                
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
    else:
        form = NewPasswordForm()
    
    return render(request, 'reset_password.html', {'form': form})

# ========================================================
# Member Views (Login Required)
# ========================================================

@login_required
def dashboard(request):
    """Dashboard accessible to all authenticated users"""
    try:
        # Get user profile and membership data
        user_profile = UserProfile.objects.get(user=request.user)
        user_membership = UserMembership.objects.select_related('plan').get(user=request.user)
        payments = Payment.objects.filter(user=request.user).order_by('-created_at')[:5]
        recent_activity = ActivityLog.objects.filter(user=request.user).order_by('-timestamp')[:10]
        
        # Get membership statistics
        total_members = User.objects.filter(userprofile__user_type="member").count()
        active_members = UserMembership.objects.filter(status='active').count()
        
        context = {
            'user_profile': user_profile,
            'user_membership': user_membership,
            'payments': payments,
            'recent_activity': recent_activity,
            'total_members': total_members,
            'active_members': active_members,
        }
        
    except (UserProfile.DoesNotExist, UserMembership.DoesNotExist):
        # User doesn't have profile or membership yet - still show dashboard
        user_profile = None
        user_membership = None
        
        context = {
            'user_profile': user_profile,
            'user_membership': user_membership,
            'payments': [],
            'recent_activity': [],
            'total_members': User.objects.filter(userprofile__user_type='member').count(),
            'active_members': UserMembership.objects.filter(status='active').count(),
        }
        messages.info(request, 'Complete your profile and choose a membership plan!')
    
    return render(request, 'dashboard.html', context)
@login_required
def profile(request):
    """Member profile management"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    # Get user membership info for display
    try:
        user_membership = UserMembership.objects.get(user=request.user)
    except UserMembership.DoesNotExist:
        user_membership = None
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=user_profile)
    
    return render(request, 'profile.html', {
        'form': form, 
        'user_profile': user_profile,
        'user_membership': user_membership
    })
@login_required
def membership_plans(request):
    """View all active membership plans"""
    # Get all active plans
    all_active_plans = MembershipPlan.objects.filter(is_active=True)
    
    # Get user's current plan tier if they have one
    current_plan_tier = None
    try:
        user_membership = UserMembership.objects.get(user=request.user)
        if user_membership.plan:
            current_plan_tier = user_membership.plan.tier
    except UserMembership.DoesNotExist:
        pass
    
    context = {
        'current_plan': current_plan_tier,
        'available_plans': all_active_plans,  # Show ALL active plans
    }
    return render(request, 'membership.html', context)
@login_required
def upgrade_membership(request, tier):
    """Handle membership upgrade requests"""
    try:
        # Get the membership plan (this validates the tier exists and is active)
        membership_plan = MembershipPlan.objects.get(tier=tier, is_active=True)
        
        # Check if user already has this plan
        try:
            user_membership = UserMembership.objects.get(user=request.user)
            if user_membership.plan and user_membership.plan.tier == tier:
                messages.info(request, f'You already have the {tier} membership.')
                return redirect('membership_plans')
        except UserMembership.DoesNotExist:
            # User doesn't have a membership yet - that's fine
            pass
        
        # Redirect to currency selection
        return redirect('currency_selection', plan_id=membership_plan.id)
        
    except MembershipPlan.DoesNotExist:
        messages.error(request, f'{tier.title()} membership plan is not available.')
        return redirect('membership_plans')
    except Exception as e:
        messages.error(request, 'An error occurred. Please try again.')
        return redirect('membership_plans')
@login_required
def currency_selection(request, plan_id):
    """Select currency for payment"""
    membership_plan = get_object_or_404(MembershipPlan, id=plan_id, is_active=True)
    
    if request.method == 'POST':
        currency = request.POST.get('currency')
        if currency in ['USD', 'EUR', 'GBP']:
            return redirect('payment', plan_id=plan_id, currency=currency)
        else:
            messages.error(request, 'Invalid currency selected.')
    
    context = {
        'membership_plan': membership_plan,
    }
    return render(request, 'currency_selection.html', context)

@login_required
def payment(request, plan_id, currency):
    """Process payment"""
    membership_plan = get_object_or_404(MembershipPlan, id=plan_id, is_active=True)
    
    # Convert price based on currency
    conversion_rates = {'USD': 1.0, 'EUR': 0.85, 'GBP': 0.75}
    if currency not in conversion_rates:
        messages.error(request, 'Invalid currency.')
        return redirect('currency_selection', plan_id=plan_id)
    
    amount = float(membership_plan.price) * conversion_rates[currency]
    amount_cents = int(amount * 100)
    amount_display = Decimal(amount).quantize(Decimal('0.00'))
    
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                token = form.cleaned_data['stripe_token']
                
                charge = stripe.Charge.create(
                    amount=amount_cents,
                    currency=currency.lower(),
                    description=f'{membership_plan.tier.title()} Membership - {membership_plan.name}',
                    source=token,
                )
                
                if charge.status == 'succeeded':
                    # Update or create user membership
                    user_membership, created = UserMembership.objects.get_or_create(
                        user=request.user,
                        defaults={'plan': membership_plan, 'status': 'active'}
                    )
                    
                    if not created:
                        user_membership.plan = membership_plan
                        user_membership.status = 'active'
                        user_membership.save()
                    
                    # Record payment
                    Payment.objects.create(
                        user=request.user,
                        user_membership=user_membership,
                        amount=amount_display,
                        currency=currency,
                        stripe_payment_intent_id=charge.id,
                        status='succeeded',
                        description=f'{membership_plan.tier.title()} Membership Payment'
                    )
                    
                    # Log payment activity
                    log_activity(
                        request.user,
                        'payment',
                        f'Successfully upgraded to {membership_plan.tier} membership'
                    )
                    
                    messages.success(request, f'Successfully upgraded to {membership_plan.tier} membership!')
                    return redirect('payment_success')
                else:
                    messages.error(request, 'Payment failed. Please try again.')
                    
            except stripe.error.StripeError as e:
                messages.error(request, f'Payment error: {str(e)}')
            except Exception as e:
                messages.error(request, 'An unexpected error occurred.')
    else:
        form = PaymentForm()
    
    context = {
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY,
        'membership_plan': membership_plan,
        'amount': amount_cents,
        'currency': currency,
        'amount_display': amount_display,
        'currency_display': currency.upper(),
        'form': form,
    }
    
    return render(request, 'payment.html', context)

@login_required
def payment_success(request):
    """Payment success page"""
    return render(request, 'payment_success.html')

@login_required
def payment_history(request):
    """View payment history"""
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'payment_history.html', {'payments': payments})

@login_required
def cancel_membership(request):
    """Cancel membership"""
    try:
        user_membership = UserMembership.objects.get(user=request.user)
        
        if request.method == 'POST':
            user_membership.status = 'cancelled'
            user_membership.cancel_at_period_end = True
            user_membership.save()
            
            log_activity(
                request.user,
                'membership_cancelled',
                'Membership cancellation requested'
            )
            
            messages.success(request, 'Your membership cancellation request has been processed.')
            return redirect('dashboard')
        
        context = {
            'user_membership': user_membership,
        }
        return render(request, 'cancel_membership.html', context)
        
    except UserMembership.DoesNotExist:
        messages.error(request, 'No active membership found.')
        return redirect('dashboard')

# ========================================================
# Admin Views
# ========================================================

@login_required
@user_passes_test(lambda u: u.is_superuser or is_admin(u))
def admin_dashboard(request):
    """Admin dashboard"""
    total_members = User.objects.filter(userprofile__user_type='member').count()
    active_members = UserMembership.objects.filter(status='active').count()
    total_revenue = Payment.objects.filter(status='succeeded').aggregate(
        total= sum('amount')
    )['total'] or 0
    
    context = {
        'total_members': total_members,
        'active_members': active_members,
        'total_revenue': total_revenue,
    }
    
    return render(request, 'admin_dashboard.html', context)

# ========================================================
# Logout View
# ========================================================

def logout_view(request):
    """User logout"""
    if request.user.is_authenticated:
        log_activity(
            request.user, 
            'logout', 
            f'User logged out',
            request.META.get('REMOTE_ADDR')
        )
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('homepage')

# ========================================================
# Error Handlers
# ========================================================

def handler404(request, exception):
    return render(request, '404.html', status=404)

def handler500(request):
    return render(request, '500.html', status=500)

def handler403(request, exception):
    return render(request, '403.html', status=403)

def handler400(request, exception):
    return render(request, '400.html', status=400)


# views.py - Add these new views
@login_required
def member_directory(request):
    """Searchable member directory"""
    search_query = request.GET.get('q', '')
    industry_filter = request.GET.get('industry', '')
    
    members = MemberDirectory.objects.filter(
        is_public=True, 
        verification_status='verified'
    ).select_related('user')
    
    if search_query:
        members = members.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(job_title__icontains=search_query) |
            Q(company__icontains=search_query) |
            Q(expertise__icontains=search_query)
        )
    
    if industry_filter:
        members = members.filter(association__industry=industry_filter)
    
    return render(request, 'member_directory.html', {
        'members': members,
        'search_query': search_query
    })

@login_required
def industry_events(request):
    """Upcoming industry events"""
    events = IndustryEvent.objects.filter(
        end_date__gte=datetime.now()
    ).order_by('start_date')
    
    return render(request, 'industry_events.html', {'events': events})

@login_required
def certification_programs(request):
    """Available certification programs"""
    certifications = CertificationProgram.objects.filter(is_active=True)
    return render(request, 'certification_programs.html', {'certifications': certifications})

@login_required
def event_registration(request, event_id):
    """Register for an event"""
    event = get_object_or_404(IndustryEvent, id=event_id)
    
    if request.method == 'POST':
        # Handle event registration and payment
        # Create registration record
        # Process payment if event has fee
        messages.success(request, f'Successfully registered for {event.title}!')
        return redirect('industry_events')
    
    return render(request, 'event_registration.html', {'event': event})