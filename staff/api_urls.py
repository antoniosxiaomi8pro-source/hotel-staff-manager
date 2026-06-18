from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import HotelViewSet, DepartmentViewSet, EmployeeViewSet, ShiftViewSet, OvertimeRuleViewSet

router = DefaultRouter()
router.register(r'hotels', HotelViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'employees', EmployeeViewSet)
router.register(r'shifts', ShiftViewSet)
router.register(r'overtime-rules', OvertimeRuleViewSet)

urlpatterns = [
    path('', include(router.urls)),
]