from django.contrib import admin
from .models import  MembershipPlan,SystemSetting,Notification,ActivityLog,Member,UserProfile,Payment,UserMembership

admin.site.register(MembershipPlan)
admin.site.register(Payment)
admin.site.register(UserProfile)
admin.site.register(Notification)
admin.site.register(ActivityLog)
admin.site.register(Member)
admin.site.register(SystemSetting)
admin.site.register(UserMembership)

