from django.contrib import admin
from .models import Subject, Exam, ExamSubject, Result
admin.site.register(Subject); admin.site.register(Exam); admin.site.register(ExamSubject)
@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display=("student","exam_subject","total_marks","grade","passed","is_synthetic")
    list_filter=("exam_subject__exam","exam_subject__subject","passed","is_synthetic")
