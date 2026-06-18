from django.urls import path
from .admin_actions import apply_global_template

urlpatterns = [
    path('apply-template/', apply_global_template, name='apply_global_template'),
]
