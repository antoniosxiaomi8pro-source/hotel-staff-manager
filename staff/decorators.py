from django.core.exceptions import PermissionDenied
from functools import wraps
from .models import Department

def manager_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)
        if Department.objects.filter(manager=request.user).exists():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view

def hr_or_manager_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)
        is_manager = Department.objects.filter(manager=request.user).exists()
        is_hr = request.user.groups.filter(name="HR").exists()
        if not (is_manager or is_hr):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def hr_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)
        if not request.user.groups.filter(name="HR").exists():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped_view
