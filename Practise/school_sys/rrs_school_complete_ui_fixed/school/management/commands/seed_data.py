from django.core.management.base import BaseCommand
from django.db import transaction

from school.models import (ClassGroup, ClassSubject, Group, SchoolClass, SchoolConfig, Section, Student, Subject,
                           Teacher, User)

# (name, name_bn, code, total, cq, short, mcq, practical, cq_pass, written_pass, mcq_pass, prac_pass, religion)
G = lambda n, bn, c: (n, bn, c, 100, 50, 20, 30, 0, 0, 23, 10, 0, "")           # general 70 + 30
P = lambda n, bn, c: (n, bn, c, 100, 40, 10, 25, 25, 13, 0, 8, 8, "")           # theory 75 + practical 25
R = lambda n, bn, c, rel: (n, bn, c, 100, 50, 20, 30, 0, 0, 23, 10, 0, rel)

SUBJECTS = [
    G("Bangla 1st Paper", "বাংলা ১ম পত্র", "101"), G("Bangla 2nd Paper", "বাংলা ২য় পত্র", "102"),
    G("English 1st Paper", "ইংরেজি ১ম পত্র", "107"), G("English 2nd Paper", "ইংরেজি ২য় পত্র", "108"),
    G("Mathematics", "গণিত", "109"),
    ("Information and Communication Technology", "তথ্য ও যোগাযোগ প্রযুক্তি", "154", 50, 0, 0, 25, 25, 0, 0, 8, 8, ""),
    P("Chemistry", "রসায়ন", "137"), P("Higher Mathematics", "উচ্চতর গণিত", "126"),
    P("Physics", "পদার্থবিজ্ঞান", "136"), P("Biology", "জীববিজ্ঞান", "138"),
    G("Bangladesh and Global Studies", "বাংলাদেশ ও বিশ্বপরিচয়", "150"),
    P("General Science", "বিজ্ঞান / সাধারণ বিজ্ঞান", "127"),
    G("Economics", "অর্থনীতি", "141"), G("Civics and Citizenship", "পৌরনীতি ও নাগরিকতা", "140"),
    G("History of Bangladesh and World Civilization", "বাংলাদেশের ইতিহাস ও বিশ্বসভ্যতা", "153"),
    G("Geography and Environment", "ভূগোল ও পরিবেশ", "110"),
    G("Accounting", "হিসাববিজ্ঞান", "146"), G("Business Entrepreneurship", "ব্যবসায় উদ্যোগ", "143"),
    G("Finance and Banking", "ফিন্যান্স ও ব্যাংকিং", "152"),
    P("Agriculture Studies", "কৃষিশিক্ষা", "134"), P("Home Science", "গার্হস্থ্য বিজ্ঞান", "151"),
    P("Fine Arts & Crafts", "চারু ও কারুকলা", "148"),
    # 50-mark subjects: NCTB doesn't publish splits here, so thresholds are scaled to 33% (see README)
    ("Career Education", "ক্যারিয়ার শিক্ষা", "156", 50, 30, 0, 20, 0, 10, 0, 7, 0, ""),
    ("Physical Education, Health Science & Sports", "শারীরিক শিক্ষা, স্বাস্থ্যবিজ্ঞান ও খেলাধুলা", "147",
     50, 25, 0, 0, 25, 8, 0, 0, 8, ""),
    R("Islam and Moral Education", "ইসলাম শিক্ষা / ইসলাম ও নৈতিক শিক্ষা", "111", "Islam"),
    R("Hindu Religion and Moral Education", "হিন্দুধর্ম শিক্ষা", "112", "Hindu"),
    R("Christian Religion and Moral Education", "খ্রিস্টধর্ম শিক্ষা", "114", "Christian"),
    R("Buddhist Religion and Moral Education", "বৌদ্ধধর্ম শিক্ষা", "113", "Buddhist"),
    G("Arabic", "আরবি", "121"), G("Sanskrit", "সংস্কৃত", "123"), G("Pali", "পালি", "124"),
    P("Music", "সঙ্গীত", "149"),
]

CLASSES = [("Six", 6), ("Seven", 7), ("Eight", 8), ("Nine", 9), ("Ten", 10)]
COMMON_6_8 = ["101", "102", "107", "108", "109", "154", "150", "127", "111", "112", "113", "114", "147", "156", "148"]
COMMON_9_10 = ["101", "102", "107", "108", "109", "154", "111", "112", "113", "114", "147", "156"]
GROUP_SUBJECTS = {
    "Science": ["136", "137", "138", "150"],
    "Arts": ["150", "127", "141", "140", "153", "110"],
    "Commerce": ["127", "146", "143", "152"],
}
OPTIONAL_9_10 = {"Science": ["126"], "Arts": ["134", "151"], "Commerce": ["134", "151"]}

TEACHERS = [
    ("Md. Shahjahan Khan", "Head Master", "shahjahan"), ("Taohidul Islam", "Computer Operator", "taohidul"),
    ("Ajkar Uddin Sikdar", "Assistant Teacher", "ajkar"), ("Md. Khalis Miah", "Assistant Teacher", "khalis"),
    ("Mitun Debnath", "Assistant Teacher", "mitun"), ("Suma Begum", "Assistant Teacher", "suma"),
    ("Md. Maynul Islam", "Assistant Teacher", "maynul"), ("Nusrot Jahan Mohim", "Assistant Teacher", "nusrot"),
    ("Rujyna Akther", "Assistant Teacher", "rujyna"), ("Rafiur Rahman Saikat", "Assistant Teacher", "rafiur"),
]

# Names from the project brief. DOB / mobile / address were not supplied -> left blank, fill via CSV import.
BRIEF_STUDENTS = ["Nusrat Jannat", "Kazi Tanjina Begum", "Esrar Jannat Nuhi", "Marjana Begum",
                  "Sanjida Begum Mili", "Mst Sadia Begum", "Tahmina Akter Tamanna"]


class Command(BaseCommand):
    help = "Seed school config, users, classes, sections, groups, 32 NCTB subjects, teachers and brief students."

    @transaction.atomic
    def handle(self, *args, **opts):
        SchoolConfig.get()

        admin, _ = User.objects.get_or_create(username="admin", defaults={
            "role": "super_admin", "is_superuser": True, "is_staff": True, "first_name": "Super Admin"})
        admin.set_password("admin123"); admin.save()
        hm, _ = User.objects.get_or_create(username="headmaster", defaults={
            "role": "headmaster", "is_staff": True, "first_name": "Md. Shahjahan Khan"})
        hm.set_password("password123"); hm.save()

        for name, desig, uname in TEACHERS:
            u, _ = User.objects.get_or_create(username=uname, defaults={"role": "teacher", "first_name": name})
            u.set_password("teacher123"); u.save()
            Teacher.objects.get_or_create(user=u, defaults={"name": name, "designation": desig})

        for row in SUBJECTS:
            n, bn, code, tot, cq, sh, mcq, pr, cqp, wp, mp, pp, rel = row
            Subject.objects.update_or_create(code=code, defaults=dict(
                name=n, name_bn=bn, total_marks=tot, cq_max=cq, short_max=sh, mcq_max=mcq, practical_max=pr,
                cq_pass=cqp, written_pass=wp, mcq_pass=mp, practical_pass=pp, religion=rel))

        groups = {n: Group.objects.get_or_create(name=n)[0] for n in ("Science", "Arts", "Commerce", "General")}
        subj = {s.code: s for s in Subject.objects.all()}

        for cname, level in CLASSES:
            cls, _ = SchoolClass.objects.get_or_create(level=level, defaults={"name": cname})
            for sec in ("A", "B"):
                Section.objects.get_or_create(school_class=cls, name=sec)
            for gname, group in groups.items():
                ClassGroup.objects.get_or_create(school_class=cls, group=group, defaults={"is_enabled": level >= 9 or gname == "General"})
            if level <= 8:
                for code in COMMON_6_8:
                    ClassSubject.objects.get_or_create(school_class=cls, subject=subj[code], group=None)
                for code in ("134", "151"):  # 4th-subject style choice for 6-8
                    ClassSubject.objects.get_or_create(school_class=cls, subject=subj[code], group=None,
                                                       defaults={"is_optional": True})
            else:
                for code in COMMON_9_10:
                    ClassSubject.objects.get_or_create(school_class=cls, subject=subj[code], group=None)
                for gname, codes in GROUP_SUBJECTS.items():
                    for code in codes:
                        ClassSubject.objects.get_or_create(school_class=cls, subject=subj[code], group=groups[gname])
                for gname, codes in OPTIONAL_9_10.items():
                    for code in codes:
                        ClassSubject.objects.get_or_create(school_class=cls, subject=subj[code], group=groups[gname],
                                                           defaults={"is_optional": True})

        ten = SchoolClass.objects.get(level=10)
        sec_a = Section.objects.get(school_class=ten, name="A")
        for i, name in enumerate(BRIEF_STUDENTS, 1):
            if not Student.objects.filter(name=name).exists():
                Student.objects.create(name=name, gender="F", school_class=ten, section=sec_a,
                                       group=groups["Science"], roll=i)
        self.stdout.write(self.style.SUCCESS(
            "Seeded. Logins: admin/admin123, headmaster/password123, <teacher>/teacher123 (e.g. shahjahan)."))
