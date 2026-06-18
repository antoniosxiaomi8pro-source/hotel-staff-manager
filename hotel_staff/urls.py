from django.contrib import admin
from django.urls import path, include
from staff.admin_actions import apply_global_template

urlpatterns = [
    path('admin/apply-template/', apply_global_template),  # ΠΡΙΝ το admin!
    path('admin/', admin.site.urls),
    path('', include('staff.urls')),
]
