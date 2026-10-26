from rest_framework import serializers
from .models import Subject, Exam, ExamSubject, Result
class SubjectSerializer(serializers.ModelSerializer):
    class Meta: model=Subject; fields="__all__"
class ExamSubjectSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    class Meta: model=ExamSubject; fields="__all__"
class ExamSerializer(serializers.ModelSerializer):
    school_classes = serializers.PrimaryKeyRelatedField(many=True, queryset=__import__("apps.academics.models",fromlist=["SchoolClass"]).SchoolClass.objects.all(), required=False)
    subject_configs = ExamSubjectSerializer(source="examsubject_set", many=True, read_only=True)
    class Meta: model=Exam; fields=["id","name","academic_year","kind","school_classes","subjects","subject_configs","is_published","created_at"]
class ResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    subject_name = serializers.CharField(source="exam_subject.subject.name", read_only=True)
    exam_name = serializers.CharField(source="exam_subject.exam.name", read_only=True)

    class Meta:
        model = Result
        fields = "__all__"
        read_only_fields = ["total_marks", "grade", "grade_point", "passed", "updated_at"]

    def validate(self, attrs):
        cfg = attrs.get("exam_subject", getattr(self.instance, "exam_subject", None))
        values = {}
        for field in ("cq_marks", "short_marks", "mcq_marks", "practical_marks"):
            values[field] = attrs.get(field, getattr(self.instance, field, 0) if self.instance else 0)
            if values[field] < 0:
                raise serializers.ValidationError({field: "Marks cannot be negative."})
        if cfg:
            limits = {"cq_marks": cfg.cq_max, "short_marks": cfg.short_max,
                      "mcq_marks": cfg.mcq_max, "practical_marks": cfg.practical_max}
            for field, maximum in limits.items():
                if values[field] > maximum:
                    raise serializers.ValidationError({field: f"Cannot exceed configured maximum ({maximum})."})
            if sum(values.values()) > cfg.total_marks:
                raise serializers.ValidationError("Component marks cannot exceed the configured total marks.")
        return attrs
