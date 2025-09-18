from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Public URLs
    path('', views.homepage, name='homepage'),
    path('pricing/', views.pricing, name='pricing'),
    path('about/', views.about, name='aboutus'),
    path('contact/', views.contact, name='contact'),
    
    # Authentication URLs
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/logout/', views.logout_view, name='logout'),
    
    # Password Reset URLs
    path('accounts/forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('accounts/confirm-code/', views.confirm_code_view, name='confirm_code'),
    path('accounts/reset-password/', views.reset_password_view, name='reset_password'),
    
    # Member URLs (Protected)
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('membership/plans/', views.membership_plans, name='membership_plans'),
    path('membership/upgrade/<str:tier>/', views.upgrade_membership, name='upgrade_membership'),
    path('membership/currency/<int:plan_id>/', views.currency_selection, name='currency_selection'),
    path('membership/payment/<int:plan_id>/<str:currency>/', views.payment, name='payment'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/history/', views.payment_history, name='payment_history'),
    path('membership/cancel/', views.cancel_membership, name='cancel_membership'),
    
    # Admin URLs (Protected)
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),     
        # Association features
    path('directory/', views.member_directory, name='member_directory'),
    path('events/', views.industry_events, name='industry_events'),
    path('events/<int:event_id>/register/', views.event_registration, name='event_registration'),
    path('certifications/', views.certification_programs, name='certification_programs'),
    # path('profile/professional/', views.professional_profile, name='professional_profile'),                                           
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Error handlers
handler404 = 'membership.views.handler404'
handler500 = 'membership.views.handler500'
handler403 = 'membership.views.handler403'
handler400 = 'membership.views.handler400'