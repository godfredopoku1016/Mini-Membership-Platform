 
# # Signal handlers
# from django.dispatch import receiver
# from django.contrib.auth.models import User

# from membership.models import Member, SystemSetting, UserProfile

# @receiver(post_save, sender=User)
# def create_user_profile(sender, instance, created, **kwargs):
#     """Automatically create user profile when a new user is created"""
#     if created:
#         UserProfile.objects.create(user=instance)

# @receiver(post_save, sender=User)
# def save_user_profile(sender, instance, **kwargs):
#     """Automatically save user profile when user is saved"""
#     if hasattr(instance, 'userprofile'):
#         instance.userprofile.save()

# @receiver(post_save, sender=UserProfile)
# def create_member_for_member_type(sender, instance, created, **kwargs):
#     """Create Member object for users with member type"""
#     if created and instance.user_type == 'member':
#         Member.objects.create(user_profile=instance)

# # Default system settings
# DEFAULT_SETTINGS = [
#     {'key': 'STRIPE_LIVE_MODE', 'value': 'False', 'description': 'Enable live Stripe mode'},
#     {'key': 'AUTO_RENEW_MEMBERSHIPS', 'value': 'True', 'description': 'Automatically renew memberships'},
#     {'key': 'ALLOW_SELF_SIGNUP', 'value': 'True', 'description': 'Allow users to sign up themselves'},
#     {'key': 'REQUIRE_EMAIL_VERIFICATION', 'value': 'True', 'description': 'Require email verification'},
# ]

# # Create default settings if they don't exist
# def create_default_settings():
#     for setting_data in DEFAULT_SETTINGS:
#         SystemSetting.objects.get_or_create(
#             key=setting_data['key'],
#             defaults={
#                 'value': setting_data['value'],
#                 'description': setting_data['description']
#             }
#         )

# # Run this when the app is ready                                                                                                                                     
# # create_default_settings()                  