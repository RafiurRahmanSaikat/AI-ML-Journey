from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.core.views import HealthView
from apps.academics.views import SchoolClassViewSet, SectionViewSet
from apps.students.views import StudentViewSet
from apps.exams.views import SubjectViewSet, ExamViewSet, ResultViewSet
from apps.documents.views import StudentCardView
router=DefaultRouter()
router.register("classes",SchoolClassViewSet)
router.register("sections",SectionViewSet)
router.register("students",StudentViewSet)
router.register("subjects",SubjectViewSet)
router.register("exams",ExamViewSet)
router.register("results",ResultViewSet)
urlpatterns=[
 path("admin/",admin.site.urls), path("api/v1/health/",HealthView.as_view()),
 path("api/v1/auth/token/",TokenObtainPairView.as_view(),name="token_obtain_pair"),
 path("api/v1/auth/token/refresh/",TokenRefreshView.as_view(),name="token_refresh"),
 path("api/v1/students/<int:student_id>/card/",StudentCardView.as_view()),
 path("api/v1/",include(router.urls)),
]
