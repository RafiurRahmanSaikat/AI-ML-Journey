from django.test import TestCase
from apps.academics.models import SchoolClass, Section
from apps.students.models import Student
from .models import Subject, Exam, ExamSubject, Result


class ResultGradingTests(TestCase):
    def setUp(self):
        school_class = SchoolClass.objects.create(name="Nine", numeric_level=9)
        section = Section.objects.create(school_class=school_class, name="A")
        self.student = Student.objects.create(name="Test Student", school_class=school_class, section=section)
        subject = Subject.objects.create(code="136", name="Physics", group="SCIENCE", total_marks=100)
        exam = Exam.objects.create(name="Test Half Yearly", academic_year=2027, kind="HALF_YEARLY")
        exam.school_classes.add(school_class)
        self.config = ExamSubject.objects.create(
            exam=exam, subject=subject, total_marks=100, cq_max=40, short_max=10,
            mcq_max=25, practical_max=25, pass_marks=33, cq_pass_marks=13,
            mcq_pass_marks=8, practical_pass_marks=8,
        )

    def test_component_failure_fails_subject_even_if_total_is_high(self):
        result = Result(
            student=self.student, exam_subject=self.config,
            cq_marks=12, short_marks=10, mcq_marks=25, practical_marks=25,
        )
        result.calculate()
        self.assertEqual(result.grade, "F")
        self.assertFalse(result.passed)

    def test_a_plus_grade(self):
        result = Result(
            student=self.student, exam_subject=self.config,
            cq_marks=40, short_marks=10, mcq_marks=25, practical_marks=25,
        )
        result.calculate()
        self.assertEqual(result.grade, "A+")
        self.assertEqual(float(result.grade_point), 5.0)
        self.assertTrue(result.passed)
