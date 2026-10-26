import csv, random
from datetime import date
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from apps.academics.models import SchoolClass, Section
from apps.students.models import Student
from apps.exams.models import Subject, Exam, ExamSubject, Result
CLASSES={"SIX":("Six",6),"SIXTH":("Six",6),"SEVEN":("Seven",7),"EIGHT":("Eight",8),"NINE":("Nine",9),"TEN":("Ten",10)}
SUBJECTS=[
("101","Bangla 1st Paper","বাংলা ১ম পত্র","COMMON",100),("102","Bangla 2nd Paper","বাংলা ২য় পত্র","COMMON",100),
("107","English 1st Paper","ইংরেজি ১ম পত্র","COMMON",100),("108","English 2nd Paper","ইংরেজি ২য় পত্র","COMMON",100),
("109","Mathematics","গণিত","COMMON",100),("154","Information and Communication Technology","তথ্য ও যোগাযোগ প্রযুক্তি","COMMON",50),
("111","Islam and Moral Education","ইসলাম ও নৈতিক শিক্ষা","COMMON",100),("112","Hindu Religion and Moral Education","হিন্দুধর্ম ও নৈতিক শিক্ষা","COMMON",100),
("113","Buddhist Religion and Moral Education","বৌদ্ধধর্ম ও নৈতিক শিক্ষা","COMMON",100),("114","Christian Religion and Moral Education","খ্রিস্টধর্ম ও নৈতিক শিক্ষা","COMMON",100),
("136","Physics","পদার্থবিজ্ঞান","SCIENCE",100),("137","Chemistry","রসায়ন","SCIENCE",100),("138","Biology","জীববিজ্ঞান","SCIENCE",100),
("150","Bangladesh and Global Studies","বাংলাদেশ ও বিশ্বপরিচয়","COMMON",100),("153","History of Bangladesh and World Civilization","বাংলাদেশের ইতিহাস ও বিশ্বসভ্যতা","HUMANITIES",100),
("110","Geography and Environment","ভূগোল ও পরিবেশ","HUMANITIES",100),("140","Civics and Citizenship","পৌরনীতি ও নাগরিকতা","HUMANITIES",100),
("127","General Science","সাধারণ বিজ্ঞান","HUMANITIES",100),("146","Accounting","হিসাববিজ্ঞান","BUSINESS",100),
("152","Finance and Banking","ফিন্যান্স ও ব্যাংকিং","BUSINESS",100),("143","Business Entrepreneurship","ব্যবসায় উদ্যোগ","BUSINESS",100),
("126","Higher Mathematics","উচ্চতর গণিত","OPTIONAL",100),("134","Agriculture Studies","কৃষিশিক্ষা","OPTIONAL",100),
("151","Home Science","গার্হস্থ্য বিজ্ঞান","OPTIONAL",100),("141","Economics","অর্থনীতি","OPTIONAL",100)]
def clean(v): return (v or "").strip()
def parse_date(v):
    v=clean(v)
    if not v or v in {"-","0001-01-01","0020-09-08","0013-12-30"}: return None
    try:
        d=date.fromisoformat(v)
        if d.year < 1900: return None
        return d
    except ValueError: return None
class Command(BaseCommand):
    help="Seed school classes, sections, subjects, accounts, CSV students and clearly-marked demo results."
    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(Path(__file__).resolve().parents[4]/"data"/"students_source.csv"))
        parser.add_argument("--reset-demo-results", action="store_true")
    def handle(self,*args,**opts):
        random.seed(20271014)
        classes={}
        for label,(name,num) in CLASSES.items():
            obj,_=SchoolClass.objects.get_or_create(numeric_level=num,defaults={"name":name})
            classes[name]=obj
            for sec in ["A","B"]: Section.objects.get_or_create(school_class=obj,name=sec)
        groups={}
        for name in ["Admin","Headmaster"]:
            groups[name],_=Group.objects.get_or_create(name=name)
        for username,group_name in [("admin","Admin"),("headmaster","Headmaster")]:
            user,_=User.objects.get_or_create(username=username,defaults={"first_name":group_name,"is_staff":True,"is_active":True})
            user.set_password("password123"); user.is_staff=True; user.is_active=True; user.save()
            user.groups.add(groups[group_name])
        subject_objects={}
        for code,name,bn,group,total in SUBJECTS:
            subject_objects[code],_=Subject.objects.update_or_create(code=code,defaults={"name":name,"name_bn":bn,"group":group,"total_marks":total})
        path=Path(opts["csv"])
        if not path.exists(): raise RuntimeError(f"CSV not found: {path}")
        with path.open(encoding="utf-8-sig",newline="") as f:
            reader=csv.DictReader(f)
            rows=list(reader)
        created=0; skipped=0; seen_roll={}
        for row in rows:
            raw_class=clean(row.get("Class")).upper()
            if raw_class not in CLASSES: skipped+=1; continue
            cls_name,level=CLASSES[raw_class]; cls=classes[cls_name]
            sec_name=clean(row.get("Section")).upper() or "A"
            sec,_=Section.objects.get_or_create(school_class=cls,name=sec_name)
            try: roll=int(clean(row.get("Roll"))) or None
            except ValueError: roll=None
            # The source contains no group field. Seed Science/Humanities only; make allocation explicit and deterministic.
            group="SCIENCE" if level in (9,10) and (roll or 0)%2==0 else "HUMANITIES"
            name=clean(row.get("Name"))
            if not name: skipped+=1; continue
            phone=clean(row.get("Phone")).replace('="','').replace('"','')
            phone=re_sub_phone(phone)
            values={"roll":roll,"name":name,"father_name":clean(row.get("Father Name")),
                "father_name_bn":clean(row.get("Father Name (Bangla)")),"mother_name":clean(row.get("Mother Name")),
                "mother_name_bn":clean(row.get("Mother Name (Bangla)")),"school_class":cls,"section":sec,"group":group,
                "date_of_birth":parse_date(row.get("Date of Birth")),"phone":phone,"address":clean(row.get("Address"))}
            # Preserve repeatable seeding and source row identity.
            existing=Student.objects.filter(name=name,school_class=cls,section=sec,roll=roll).first()
            if existing:
                for k,v in values.items(): setattr(existing,k,v)
                existing.save(); continue
            Student.objects.create(**values); created+=1
        # Demo subject selection: configure a manageable, school-editable set per exam.
        students=list(Student.objects.filter(active=True).select_related("school_class"))
        def subjects_for(student):
            common=["101","102","107","108","109","154","111","150"]
            if student.school_class.numeric_level in (9,10):
                extra=["136","137","138"] if student.group=="SCIENCE" else ["153","110","140"]
            else: extra=["127"]
            return common+extra
        def exam_for(name,year,kind,levels):
            exam,_=Exam.objects.get_or_create(name=name,academic_year=year,defaults={"kind":kind})
            exam.kind=kind; exam.save()
            exam.school_classes.set([c for c in classes.values() if c.numeric_level in levels])
            selected=set()
            for s in students:
                if s.school_class.numeric_level not in levels: continue
                for code in subjects_for(s): selected.add(code)
            for code in sorted(selected):
                subj=subject_objects[code]
                if code=="154":
                    cfg,_=ExamSubject.objects.get_or_create(exam=exam,subject=subj,defaults={"total_marks":50,"cq_max":0,"short_max":0,"mcq_max":25,"practical_max":25,"pass_marks":17,"cq_pass_marks":0,"mcq_pass_marks":8,"practical_pass_marks":8})
                elif code in {"136","137","138","126","134","151"}:
                    cfg,_=ExamSubject.objects.get_or_create(exam=exam,subject=subj,defaults={"total_marks":100,"cq_max":40,"short_max":10,"mcq_max":25,"practical_max":25,"pass_marks":33,"cq_pass_marks":13,"mcq_pass_marks":8,"practical_pass_marks":8})
                else:
                    cfg,_=ExamSubject.objects.get_or_create(exam=exam,subject=subj,defaults={"total_marks":100,"cq_max":50,"short_max":20,"mcq_max":30,"practical_max":0,"pass_marks":33,"written_pass_marks":23,"cq_pass_marks":0,"mcq_pass_marks":10,"practical_pass_marks":0})
            return exam
        exams=[exam_for("Annual Examination",2025,"ANNUAL",[6,7,8,9,10]),
               exam_for("Half Yearly Examination",2025,"HALF_YEARLY",[6,7,8,9,10]),
               exam_for("Half Yearly Examination",2027,"HALF_YEARLY",[6,7,8,9,10]),
               exam_for("Pre Test Examination",2027,"PRE_TEST",[10]),
               exam_for("Model Test Examination",2027,"MODEL_TEST",[10]),
               exam_for("Test Examination",2027,"TEST",[10])]
        # Grade-looking but fake values are deterministic and explicitly marked synthetic.
        completed_exams=[e for e in exams if e.kind in {"ANNUAL", "HALF_YEARLY"}]
        for exam in completed_exams:
            cfgs=list(ExamSubject.objects.filter(exam=exam).select_related("subject"))
            for student in students:
                if not exam.school_classes.filter(pk=student.school_class_id).exists(): continue
                allowed=set(subjects_for(student))
                for cfg in cfgs:
                    if cfg.subject.code not in allowed: continue
                    if Result.objects.filter(student=student,exam_subject=cfg).exists(): continue
                    total=cfg.total_marks
                    if cfg.subject.code=="154":
                        practical=random.randint(8,25); mcq=random.randint(8,25); cq=0; short=0
                    elif cfg.practical_max:
                        practical=random.randint(max(cfg.practical_pass_marks,8),cfg.practical_max)
                        mcq=random.randint(max(cfg.mcq_pass_marks,8),cfg.mcq_max)
                        cq=random.randint(max(cfg.cq_pass_marks,13),cfg.cq_max)
                        short=random.randint(0,cfg.short_max)
                    else:
                        practical=0; cq=random.randint(23,50); short=random.randint(0,20); mcq=random.randint(10,30)
                    result=Result(student=student,exam_subject=cfg,cq_marks=cq,short_marks=short,mcq_marks=mcq,practical_marks=practical,is_synthetic=True)
                    result.save()
        self.stdout.write(self.style.SUCCESS(f"Seed complete. Students created this run: {created}; skipped rows: {skipped}; total students: {Student.objects.count()}; synthetic result records: {Result.objects.filter(is_synthetic=True).count()}. Accounts: admin/headmaster / password123"))
def re_sub_phone(value):
    value=value.strip()
    return value if value and value.lower() not in {"none","nan"} else ""
