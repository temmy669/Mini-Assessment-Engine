from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CourseViewSet, ExamViewSet, SubmissionViewSet,
    ExamSubmissionView, StudentDashboardView
)

app_name = 'exams'

# Router for ViewSets
router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'exams', ExamViewSet, basename='exam')
router.register(r'submissions', SubmissionViewSet, basename='submission')

urlpatterns = [
    # ViewSet URLs
    path('', include(router.urls)),
    
    # Custom endpoints
    path(
        'exams/<int:exam_id>/submit/',
        ExamSubmissionView.as_view(),
        name='exam-submit'
    ),
    path(
        'dashboard/',
        StudentDashboardView.as_view(),
        name='student-dashboard'
    ),
]