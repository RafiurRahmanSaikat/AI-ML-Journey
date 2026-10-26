from rest_framework import serializers

from . import models


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = ["id", "username", "first_name", "last_name", "role", "is_superuser"]


class SchoolConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SchoolConfig
        fields = "__all__"

    def validate_grading_scale(self, value):
        for row in value:
            if not {"min", "max", "grade", "gp"} <= set(row):
                raise serializers.ValidationError("Each row needs min, max, grade, gp.")
        return value


class SchoolClassSerializer(serializers.ModelSerializer):
    student_count = serializers.IntegerField(source="students.count", read_only=True)

    class Meta:
        model = models.SchoolClass
        fields = ["id", "name", "level", "student_count", "group_settings"]


class ClassGroupSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = models.ClassGroup
        fields = "__all__"


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Group
        fields = "__all__"


class SectionSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    student_count = serializers.IntegerField(source="students.count", read_only=True)

    class Meta:
        model = models.Section
        fields = ["id", "school_class", "class_name", "name", "student_count"]


class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Teacher
        fields = "__all__"


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Subject
        fields = "__all__"


class ClassSubjectSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)

    class Meta:
        model = models.ClassSubject
        fields = "__all__"


class StudentSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True, default=None)
    group_name = serializers.CharField(source="group.name", read_only=True, default=None)

    class Meta:
        model = models.Student
        fields = "__all__"
        read_only_fields = ["student_id", "registration_no", "user"]

    def validate(self, attrs):
        section = attrs.get("section")
        cls = attrs.get("school_class") or (self.instance.school_class if self.instance else None)
        if section and cls and section.school_class_id != cls.id:
            raise serializers.ValidationError("Section does not belong to the selected class.")
        return attrs


class ExamSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="school_class.name", read_only=True)

    class Meta:
        model = models.Exam
        fields = "__all__"


class MarkSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    total = serializers.DecimalField(max_digits=6, decimal_places=1, read_only=True)

    class Meta:
        model = models.Mark
        fields = "__all__"

    def validate(self, attrs):
        subject = attrs.get("subject") or (self.instance.subject if self.instance else None)
        errors = {}
        if subject:
            exam = attrs.get("exam") or (self.instance.exam if self.instance else None)
            custom = (exam.component_distribution or {}).get(subject.code, {}) if exam else {}
            for comp in ("cq", "short", "mcq", "practical", "continuous_assessment", "viva", "assignment"):
                val = attrs.get(comp)
                if val is None:
                    continue
                default_max = getattr(subject, f"{comp}_max", 0)
                maximum = custom.get(comp, default_max)
                if val > maximum:
                    errors[comp] = f"Cannot exceed configured {comp} maximum {maximum} for {subject.code}."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
