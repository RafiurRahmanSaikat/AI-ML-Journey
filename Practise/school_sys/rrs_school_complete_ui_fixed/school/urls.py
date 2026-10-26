from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("classes", views.ClassViewSet)
router.register("groups", views.GroupViewSet)
router.register("class-groups", views.ClassGroupViewSet)
router.register("sections", views.SectionViewSet)
router.register("teachers", views.TeacherViewSet)
router.register("subjects", views.SubjectViewSet)
router.register("class-subjects", views.ClassSubjectViewSet)
router.register("students", views.StudentViewSet)
router.register("exams", views.ExamViewSet)
router.register("marks", views.MarkViewSet)

urlpatterns = [
    path("auth/login/", views.login),
    path("auth/me/", views.me),
    path("config/", views.school_config),
    path("academic-context/", views.academic_context),
    path("results/", views.ResultView.as_view()),
    path("documents/id-cards/", views.BatchIDCardsView.as_view()),
    path("documents/<str:kind>/<int:pk>/", views.DocumentView.as_view()),
    path("", include(router.urls)),
]
