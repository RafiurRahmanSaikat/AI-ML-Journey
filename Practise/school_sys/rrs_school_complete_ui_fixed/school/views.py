from django.contrib.auth import authenticate
from django.db import transaction
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import models, serializers
from .permissions import is_admin
from .services import documents, importexport
from .services.result_engine import applicable_class_subjects, compute_exam_results, compute_result


# ------------------------------------------------------------------ auth
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    user = authenticate(username=request.data.get("username"), password=request.data.get("password"))
    if not user:
        return Response({"detail": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": serializers.UserSerializer(user).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(serializers.UserSerializer(request.user).data)


@api_view(["GET", "PUT", "PATCH"])
def school_config(request):
    """Singleton settings. Anyone logged in can read, admins can edit."""
    cfg = models.SchoolConfig.get()
    if request.method == "GET":
        return Response(serializers.SchoolConfigSerializer(cfg, context={"request": request}).data)
    if not is_admin(request.user):
        raise PermissionDenied()
    ser = serializers.SchoolConfigSerializer(cfg, data=request.data, partial=True, context={"request": request})
    ser.is_valid(raise_exception=True)
    ser.save()
    return Response(ser.data)


# ------------------------------------------------------------------ CRUD


class ClassViewSet(viewsets.ModelViewSet):
    queryset = models.SchoolClass.objects.all()
    serializer_class = serializers.SchoolClassSerializer


class GroupViewSet(viewsets.ModelViewSet):
    queryset = models.Group.objects.all()
    serializer_class = serializers.GroupSerializer


class ClassGroupViewSet(viewsets.ModelViewSet):
    queryset = models.ClassGroup.objects.select_related("school_class", "group")
    serializer_class = serializers.ClassGroupSerializer
    filterset_fields = ["school_class", "group", "is_enabled"]


class SectionViewSet(viewsets.ModelViewSet):
    queryset = models.Section.objects.select_related("school_class")
    serializer_class = serializers.SectionSerializer
    filterset_fields = ["school_class"]

    def get_queryset(self):
        qs = super().get_queryset()
        cls = self.request.query_params.get("school_class")
        return qs.filter(school_class_id=cls) if cls else qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        count = instance.students.count()
        if count:
            return Response({"detail": f"Section has {count} students. Reassign/merge them first using POST /api/sections/{instance.pk}/merge/ with {{\"into\": target_section_id}}.", "students": count, "requires_reassignment": True}, status=409)
        instance.delete()
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def merge(self, request, pk=None):
        """POST {"into": <section_id>} -> moves all students, then deletes this section."""
        src = self.get_object()
        target = models.Section.objects.filter(pk=request.data.get("into"), school_class=src.school_class).first()
        if not target or target.pk == src.pk:
            return Response({"detail": "'into' must be another section of the same class."}, status=400)
        with transaction.atomic():
            moved = src.students.update(section=target)
            src.delete()
        return Response({"moved": moved, "into": target.id})


class TeacherViewSet(viewsets.ModelViewSet):
    queryset = models.Teacher.objects.all()
    serializer_class = serializers.TeacherSerializer


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = models.Subject.objects.all()
    serializer_class = serializers.SubjectSerializer


class ClassSubjectViewSet(viewsets.ModelViewSet):
    queryset = models.ClassSubject.objects.select_related("subject", "school_class")
    serializer_class = serializers.ClassSubjectSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("school_class"):
            qs = qs.filter(school_class_id=p["school_class"])
        if p.get("group"):
            qs = qs.filter(group_id=p["group"])
        return qs


class StudentViewSet(viewsets.ModelViewSet):
    queryset = models.Student.objects.select_related("school_class", "section", "group")
    serializer_class = serializers.StudentSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "student" and not is_admin(user):
            return qs.filter(user=user)
        p = self.request.query_params
        for key in ("school_class", "section", "group"):
            if p.get(key):
                qs = qs.filter(**{f"{key}_id": p[key]})
        if p.get("search"):
            qs = qs.filter(name__icontains=p["search"]) | qs.filter(student_id__icontains=p["search"])
        return qs

    @action(detail=False, methods=["post"])
    def move(self, request):
        """POST {"student_ids": [..], "section": <id|null>} -> move students between sections."""
        ids = request.data.get("student_ids") or []
        section = None
        if request.data.get("section"):
            section = models.Section.objects.filter(pk=request.data["section"]).first()
            if not section:
                return Response({"detail": "Unknown section."}, status=400)
        qs = models.Student.objects.filter(pk__in=ids)
        if section:
            qs = qs.filter(school_class=section.school_class)
        return Response({"moved": qs.update(section=section)})

    @action(detail=False, methods=["post"])
    def promote(self, request):
        """Manual transfer or automatic annual promotion. Pass exam id for pass-filtered promotion."""
        ids = request.data.get("student_ids") or []
        exam = None
        if request.data.get("exam"):
            exam = models.Exam.objects.filter(pk=request.data.get("exam")).first()
            if not exam:
                return Response({"detail": "Unknown exam."}, status=400)
            if not ids:
                ids = list(models.Student.objects.filter(school_class=exam.school_class, is_active=True).values_list("pk", flat=True))
            from .services.result_engine import compute_result
            passed = []
            for student in models.Student.objects.filter(pk__in=ids, school_class=exam.school_class):
                if compute_result(student, exam)["status"] == "Passed":
                    passed.append(student.pk)
            ids = passed
        target_class = models.SchoolClass.objects.filter(pk=request.data.get("target_class")).first() if request.data.get("target_class") else None
        if not target_class and exam:
            if exam.exam_type != models.Exam.Type.ANNUAL:
                return Response({"detail": "Automatic next-class promotion requires an annual exam. Provide target_class for a manual transfer."}, status=400)
            target_class = models.SchoolClass.objects.filter(level=exam.school_class.level + 1).first()
        if not target_class:
            return Response({"detail": "Provide target_class (manual promotion/demotion) or a non-terminal annual exam."}, status=400)
        target_section = None
        if request.data.get("section"):
            target_section = models.Section.objects.filter(pk=request.data["section"], school_class=target_class).first()
            if not target_section:
                return Response({"detail": "Target section must belong to target class."}, status=400)
        target_group = models.Group.objects.filter(pk=request.data.get("group")).first() if request.data.get("group") else None
        year = str(request.data.get("academic_year") or (int(exam.academic_year) + 1 if exam and exam.academic_year.isdigit() else models.SchoolConfig.get().current_academic_year))
        with transaction.atomic():
            qs = models.Student.objects.filter(pk__in=ids)
            changes = {"school_class": target_class, "academic_year": year}
            if "section" in request.data or target_class.pk != (exam.school_class_id if exam else target_class.pk):
                changes["section"] = target_section
            if "group" in request.data or target_class.pk != (exam.school_class_id if exam else target_class.pk):
                changes["group"] = target_group
            changed = qs.update(**changes)
        return Response({"moved": changed, "target_class": target_class.name, "academic_year": year,
                         "filtered_to_passed_students": bool(exam), "exam": exam.id if exam else None})

    @action(detail=False, methods=["get"])
    def export(self, request):
        return importexport.export_students(self.filter_queryset(self.get_queryset()),
                                            request.query_params.get("file_type", "csv"))

    @action(detail=False, methods=["post"], url_path="import")
    def import_file(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response({"detail": "Upload a CSV/XLSX as 'file'."}, status=400)
        try:
            return Response(importexport.import_students(importexport.read_rows(f)))
        except (ValueError, UnicodeDecodeError) as exc:
            return Response({"detail": str(exc)}, status=400)


class ExamViewSet(viewsets.ModelViewSet):
    queryset = models.Exam.objects.select_related("school_class")
    serializer_class = serializers.ExamSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        for key in ("school_class", "academic_year", "exam_type"):
            v = self.request.query_params.get(key)
            if v:
                qs = qs.filter(**{(key + "_id") if key == "school_class" else key: v})
        return qs

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """Class-wide results with merit positions. ?section=<id>"""
        exam = self.get_object()
        return Response(compute_exam_results(exam, request.query_params.get("section")))


class MarkViewSet(viewsets.ModelViewSet):
    teacher_can_write = True
    queryset = models.Mark.objects.select_related("student", "subject", "exam")
    serializer_class = serializers.MarkSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "student" and not is_admin(user):
            qs = qs.filter(student__user=user)
        p = self.request.query_params
        for key in ("exam", "student", "subject"):
            if p.get(key):
                qs = qs.filter(**{f"{key}_id": p[key]})
        for key in ("school_class", "section", "group"):
            if p.get(key):
                qs = qs.filter(**{f"student__{key}_id": p[key]})
        return qs

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        """POST {"exam": id, "entries": [{"student": id, "subject": id, "cq":..,"short":..,"mcq":..,"practical":..,"absent":false}]}"""
        exam = request.data.get("exam")
        saved, errors = 0, []
        with transaction.atomic():
            for i, e in enumerate(request.data.get("entries", [])):
                existing = models.Mark.objects.filter(exam_id=exam, student_id=e.get("student"),
                                                      subject_id=e.get("subject")).first()
                ser = serializers.MarkSerializer(existing, data={**e, "exam": exam}, partial=bool(existing))
                if ser.is_valid():
                    ser.save()
                    saved += 1
                else:
                    errors.append({"index": i, "errors": ser.errors})
        return Response({"saved": saved, "errors": errors})

    @action(detail=False, methods=["get"])
    def export(self, request):
        return importexport.export_marks(self.filter_queryset(self.get_queryset()),
                                         request.query_params.get("file_type", "csv"))

    @action(detail=False, methods=["get"])
    def template(self, request):
        """Download a blank mark-entry sheet for an exam/subject and optional scope filters."""
        exam = models.Exam.objects.filter(pk=request.query_params.get("exam")).select_related("school_class").first()
        subject = models.Subject.objects.filter(pk=request.query_params.get("subject")).first()
        if not exam or not subject:
            return Response({"detail": "Valid exam and subject are required."}, status=400)
        students = models.Student.objects.filter(school_class=exam.school_class, is_active=True).select_related("section", "group")
        if request.query_params.get("section"):
            students = students.filter(section_id=request.query_params["section"])
        if request.query_params.get("group"):
            students = students.filter(group_id=request.query_params["group"])
        students = students.order_by("section__name", "group__name", "roll", "name")
        columns = ["student_id", "name", "roll", "subject_code", "cq", "short", "mcq", "practical", "continuous_assessment", "viva", "assignment", "absent"]
        rows = [[st.student_id, st.name, st.roll or "", subject.code, "", "", "", "", "", "", "", ""] for st in students]
        return importexport.write_response(columns, rows, request.query_params.get("file_type", "csv"), f"marks-template-{exam.id}-{subject.code}")

    @action(detail=False, methods=["post"], url_path="import")
    def import_file(self, request):
        exam = models.Exam.objects.filter(pk=request.data.get("exam")).first()
        f = request.FILES.get("file")
        if not exam or not f:
            return Response({"detail": "Provide 'exam' (id) and a CSV/XLSX 'file'."}, status=400)
        try:
            return Response(importexport.import_marks(importexport.read_rows(f), exam))
        except (ValueError, UnicodeDecodeError) as exc:
            return Response({"detail": str(exc)}, status=400)


@api_view(["GET"])
def academic_context(request):
    """Dynamic form payload for a selected class or exam; frontend can reload without navigation."""
    exam = models.Exam.objects.filter(pk=request.query_params.get("exam")).select_related("school_class").first() if request.query_params.get("exam") else None
    cls = exam.school_class if exam else models.SchoolClass.objects.filter(pk=request.query_params.get("school_class")).first()
    if not cls:
        return Response({"detail": "Provide a valid school_class or exam id."}, status=400)
    students = models.Student.objects.filter(school_class=cls, is_active=True).select_related("section", "group").order_by("section__name", "group__name", "roll", "name")
    if request.query_params.get("section"):
        students = students.filter(section_id=request.query_params["section"])
    if request.query_params.get("group"):
        students = students.filter(group_id=request.query_params["group"])
    subjects = models.ClassSubject.objects.filter(school_class=cls, is_enabled=True).select_related("subject", "group").order_by("subject__code")
    if request.query_params.get("group"):
        subjects = subjects.filter(models.Q(group__isnull=True) | models.Q(group_id=request.query_params["group"]))
    return Response({"class": {"id": cls.id, "name": cls.name, "level": cls.level},
        "exam": ({"id": exam.id, "name": exam.name, "academic_year": exam.academic_year, "pass_mark": exam.pass_mark,
                  "component_distribution": exam.component_distribution, "grading_scale": exam.grading_scale} if exam else None),
        "students": [{"id": x.id, "student_id": x.student_id, "name": x.name, "roll": x.roll,
                      "section": x.section.name if x.section else None, "group": x.group.name if x.group else None} for x in students],
        "subjects": [{"id": x.subject_id, "code": x.subject.code, "name": x.subject.name, "group": x.group.name if x.group else None,
                      "is_optional": x.is_optional, "distribution": {"cq": x.subject.cq_max, "short": x.subject.short_max,
                      "mcq": x.subject.mcq_max, "practical": x.subject.practical_max, "continuous_assessment": 0,
                      "viva": 0, "assignment": 0, "total": x.subject.total_marks,
                      **((exam.component_distribution or {}).get(x.subject.code, {} ) if exam else {})}} for x in subjects],
        "existing_marks": ([{"student": m.student_id, "subject": m.subject_id, "cq": float(m.cq), "short": float(m.short),
                             "mcq": float(m.mcq), "practical": float(m.practical),
                             "continuous_assessment": float(m.continuous_assessment), "viva": float(m.viva),
                             "assignment": float(m.assignment), "absent": m.absent}
                            for m in models.Mark.objects.filter(exam=exam, student__in=students)] if exam else [])})


# ------------------------------------------------------------------ results & documents
def _check_student_access(request, student):
    user = request.user
    if user.role == "student" and not is_admin(user) and student.user_id != user.id:
        raise PermissionDenied("You can only view your own records.")


class ResultView(APIView):
    """Detailed single-student result or filtered class results.

    GET /api/results/?exam=<id> supports class-wide results. When exam is omitted,
    the newest exam matching the selected class/year is used. Add filters such as
    gender, name, roll, section, and group to narrow the result table.
    """
    def get(self, request):
        student_id = request.query_params.get("student")
        exam_id = request.query_params.get("exam")
        exam_qs = models.Exam.objects.select_related("school_class")
        class_id = request.query_params.get("school_class") or request.query_params.get("class")
        year = request.query_params.get("academic_year") or request.query_params.get("year")
        if class_id:
            exam_qs = exam_qs.filter(school_class_id=class_id)
        if year:
            exam_qs = exam_qs.filter(academic_year=year)
        if exam_id:
            exam = exam_qs.filter(pk=exam_id).first()
        else:
            exam = exam_qs.order_by("-academic_year", "-id").first()
        if not exam:
            return Response({"detail": "No examination matches the selected class/year. Create an exam or adjust filters."}, status=404)
        if student_id:
            try:
                student = models.Student.objects.select_related("school_class", "section", "group").get(pk=student_id)
            except (models.Student.DoesNotExist, ValueError):
                return Response({"detail": "A valid student is required."}, status=400)
            _check_student_access(request, student)
            if student.school_class_id != exam.school_class_id:
                return Response({"detail": "The selected student does not belong to this exam's class."}, status=400)
            return Response(compute_result(student, exam))

        rows = compute_exam_results(exam)
        p = request.query_params
        student_ids = [row["student"]["id"] for row in rows]
        student_map = {s.id: s for s in models.Student.objects.filter(pk__in=student_ids).select_related("section", "group")}
        filtered = []
        for row in rows:
            st = row["student"]
            student = student_map.get(st["id"])
            if not student:
                continue
            if p.get("gender") and student.gender != p["gender"]:
                continue
            if p.get("name") and p["name"].lower() not in st["name"].lower():
                continue
            if p.get("roll") and str(st.get("roll") or "") != str(p["roll"]):
                continue
            if p.get("section") and str(p["section"]) not in (str(student.section_id or ""), str(student.section.name if student.section else "")):
                continue
            if p.get("group") and str(p["group"]) not in (str(student.group_id or ""), str(student.group.name if student.group else "")):
                continue
            filtered.append(row)
        return Response({
            "exam": {"id": exam.id, "name": exam.name, "academic_year": exam.academic_year,
                     "class": exam.school_class.name, "class_id": exam.school_class_id},
            "count": len(filtered), "results": filtered,
            "filters": {"school_class": class_id, "academic_year": year,
                        "gender": p.get("gender"), "name": p.get("name"), "roll": p.get("roll"),
                        "section": p.get("section"), "group": p.get("group")},
        })


class BatchIDCardsView(APIView):
    """GET /api/documents/id-cards/?output=json|pdf&school_class=&section=&group=&student="""
    def get(self, request):
        qs = models.Student.objects.filter(is_active=True).select_related("school_class", "section", "group").order_by("school_class__level", "section__name", "group__name", "roll", "name")
        for key in ("school_class", "section", "group", "student"):
            if request.query_params.get(key):
                field = "pk" if key == "student" else f"{key}_id"
                qs = qs.filter(**{field: request.query_params[key]})
        students = list(qs)
        if not students:
            return Response({"detail": "No students matched the requested scope."}, status=404)
        if request.query_params.get("output", "json") == "pdf":
            response = HttpResponse(documents.id_cards_pdf(students), content_type="application/pdf")
            response["Content-Disposition"] = 'inline; filename="rrs-student-id-cards.pdf"'
            return response
        return Response({"count": len(students), "scope": {k: request.query_params.get(k) for k in ("school_class", "section", "group", "student")},
                         "students": [documents.build_data("id-card", student) for student in students]})


class DocumentView(APIView):
    """GET /api/documents/<kind>/<id>/?output=json|pdf&exam=<id>
    kinds: id-card, staff-id-card, admit-card, registration-card, testimonial, report-card"""

    def get(self, request, kind, pk):
        if kind not in documents.RENDERERS:
            return Response({"detail": f"Unknown document. Use one of {list(documents.RENDERERS)}"}, status=404)
        model = models.Teacher if kind == "staff-id-card" else models.Student
        try:
            obj = model.objects.get(pk=pk)
        except model.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if model is models.Student:
            _check_student_access(request, obj)
        elif not is_admin(request.user):
            raise PermissionDenied()
        exam = models.Exam.objects.filter(pk=request.query_params.get("exam")).first()
        try:
            data = documents.build_data(kind, obj, exam)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        if kind == "report-card":
            ranked = compute_exam_results(exam)
            data["merit_position"] = next((r["merit_position"] for r in ranked if r["student"]["id"] == obj.id), None)
        if request.query_params.get("output", "json") == "pdf":
            resp = HttpResponse(documents.render_pdf(data), content_type="application/pdf")
            resp["Content-Disposition"] = f'inline; filename="{kind}-{pk}.pdf"'
            return resp
        for k in ("logo",):
            data["school"].pop(k, None)
        if "student" in data:
            data["student"].pop("photo", None)
        if "teacher" in data:
            data["teacher"].pop("photo", None)
        return Response(data)
