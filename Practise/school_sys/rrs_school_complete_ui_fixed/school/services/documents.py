"""Document data (JSON for the frontend) + PDF rendering (ReportLab).

Note: ReportLab's built-in fonts cannot render Bangla glyphs, so PDFs use English text.
The JSON variants include Bangla names for frontend rendering.
"""
import io
from datetime import date

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from ..models import SchoolConfig
from .result_engine import compute_result

NAVY = colors.HexColor("#1f3a5f")


def school_info(config=None):
    c = config or SchoolConfig.get()
    return {"name": c.name, "ein": c.ein, "estd": c.estd, "location": c.location, "address": c.address,
            "phone": c.phone, "email": c.email, "academic_year": c.current_academic_year,
            "headmaster": c.headmaster_name, "logo": c.logo.path if c.logo else None}


def student_brief(s):
    return {"id": s.id, "student_id": s.student_id, "name": s.name, "name_bn": s.name_bn,
            "father_name": s.father_name, "mother_name": s.mother_name,
            "dob": s.dob.isoformat() if s.dob else None, "mobile": s.mobile, "address": s.address,
            "class": s.school_class.name, "section": s.section.name if s.section else None,
            "group": s.group.name if s.group else None, "roll": s.roll,
            "registration_no": s.registration_no, "gender": s.gender,
            "photo": s.photo.path if s.photo else None}


def build_data(kind, obj, exam=None):
    data = {"kind": kind, "school": school_info(), "issued_on": date.today().isoformat()}
    if kind == "staff-id-card":
        data["teacher"] = {"id": obj.id, "name": obj.name, "designation": obj.designation,
                           "mobile": obj.mobile, "photo": obj.photo.path if obj.photo else None}
        data["qr_payload"] = f"RRS-STAFF-{obj.id}"
        return data
    data["student"] = student_brief(obj)
    data["qr_payload"] = f"{obj.student_id}|{obj.name}|{obj.school_class.name}"
    if kind in ("admit-card", "report-card"):
        if not exam:
            raise ValueError("exam is required for this document")
        data["exam"] = {"id": exam.id, "name": exam.name, "academic_year": exam.academic_year,
                        "start_date": exam.start_date.isoformat() if exam.start_date else None}
        if kind == "admit-card":
            from .result_engine import applicable_class_subjects
            data["subjects"] = [{"name": cs.subject.name, "code": cs.subject.code}
                                for cs in sorted(applicable_class_subjects(obj), key=lambda c: c.subject.code)]
        else:
            data["result"] = compute_result(obj, exam)
    if kind == "testimonial":
        pronoun = ("son", "he", "his") if obj.gender == "M" else ("daughter", "she", "her")
        data["pronoun"] = {"child": pronoun[0], "subject": pronoun[1], "possessive": pronoun[2]}
    return data


# ---------------------------------------------------------------- PDF helpers
def _qr(payload):
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _logo(c, d, x, y, size):
    if d["school"]["logo"]:
        try:
            c.drawImage(d["school"]["logo"], x, y, size, size, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass


def _letterhead(c, d, width, top):
    s = d["school"]
    _logo(c, d, 15 * mm, top - 22 * mm, 22 * mm)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(width / 2, top - 10 * mm, s["name"])
    c.setFont("Helvetica", 9.5)
    c.setFillColor(colors.black)
    c.drawCentredString(width / 2, top - 16 * mm, f'{s["location"]}  |  EIN: {s["ein"]}  |  Estd: {s["estd"]}')
    if s["address"]:
        c.drawCentredString(width / 2, top - 21 * mm, s["address"])
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.2)
    c.line(15 * mm, top - 26 * mm, width - 15 * mm, top - 26 * mm)


def _kv_table(rows, col_widths):
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 10),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def _id_card(d):
    buf = io.BytesIO()
    w, h = 85.6 * mm, 54 * mm
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setFillColor(NAVY)
    c.rect(0, h - 12 * mm, w, 12 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(w / 2, h - 6 * mm, d["school"]["name"])
    c.setFont("Helvetica", 6)
    c.drawCentredString(w / 2, h - 10 * mm, f'{d["school"]["location"]} | EIN {d["school"]["ein"]}')
    c.setFillColor(colors.black)
    if "student" in d:
        s = d["student"]
        lines = [("Name", s["name"]), ("ID", s["student_id"]),
                 ("Class", f'{s["class"]} {s["section"] or ""} {("(" + s["group"] + ")") if s["group"] else ""}'),
                 ("Roll", s["roll"] or "-"), ("Mobile", s["mobile"] or "-")]
        title = "STUDENT ID CARD"
    else:
        t = d["teacher"]
        lines = [("Name", t["name"]), ("Designation", t["designation"]), ("Mobile", t["mobile"] or "-")]
        title = "STAFF ID CARD"
    c.setFont("Helvetica-Bold", 7)
    c.drawString(5 * mm, h - 17 * mm, title)
    y = h - 23 * mm
    for k, v in lines:
        c.setFont("Helvetica-Bold", 7)
        c.drawString(5 * mm, y, f"{k}:")
        c.setFont("Helvetica", 7)
        c.drawString(20 * mm, y, str(v))
        y -= 4.5 * mm
    c.drawImage(_qr(d["qr_payload"]), w - 22 * mm, 6 * mm, 17 * mm, 17 * mm)
    c.setFont("Helvetica", 5.5)
    c.drawString(5 * mm, 3 * mm, f'Valid for academic year {d["school"]["academic_year"]}')
    c.save()
    return buf.getvalue()


def _admit_card(d):
    buf = io.BytesIO()
    w, h = A4
    c = canvas.Canvas(buf, pagesize=A4)
    _letterhead(c, d, w, h - 10 * mm)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, h - 45 * mm, f'ADMIT CARD - {d["exam"]["name"].upper()} {d["exam"]["academic_year"]}')
    s = d["student"]
    t = _kv_table([["Name", s["name"], "Student ID", s["student_id"]],
                   ["Class", s["class"], "Section / Roll", f'{s["section"] or "-"} / {s["roll"] or "-"}'],
                   ["Group", s["group"] or "-", "Registration", s["registration_no"]]],
                  [28 * mm, 60 * mm, 32 * mm, 55 * mm])
    t.wrapOn(c, w, h)
    t.drawOn(c, 15 * mm, h - 75 * mm)
    rows = [["SL", "Subject", "Code"]] + [[i, x["name"], x["code"]] for i, x in enumerate(d["subjects"], 1)]
    st = Table(rows, colWidths=[12 * mm, 120 * mm, 25 * mm], repeatRows=1)
    st.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    _, th = st.wrapOn(c, w, h)
    st.drawOn(c, 15 * mm, h - 85 * mm - th)
    c.drawImage(_qr(d["qr_payload"]), w - 45 * mm, 30 * mm, 25 * mm, 25 * mm)
    c.line(15 * mm, 30 * mm, 60 * mm, 30 * mm)
    c.setFont("Helvetica", 9)
    c.drawString(15 * mm, 25 * mm, "Class Teacher")
    c.line(80 * mm, 30 * mm, 125 * mm, 30 * mm)
    c.drawString(80 * mm, 25 * mm, f'Head Master: {d["school"]["headmaster"]}')
    c.save()
    return buf.getvalue()


def _registration_card(d):
    buf = io.BytesIO()
    w, h = A4
    c = canvas.Canvas(buf, pagesize=A4)
    _letterhead(c, d, w, h - 10 * mm)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, h - 45 * mm, "STUDENT REGISTRATION CARD")
    s = d["student"]
    t = _kv_table([["Registration No", s["registration_no"]], ["Student ID", s["student_id"]],
                   ["Name", s["name"]], ["Father's Name", s["father_name"] or "-"],
                   ["Mother's Name", s["mother_name"] or "-"], ["Date of Birth", s["dob"] or "-"],
                   ["Class / Section", f'{s["class"]} / {s["section"] or "-"}'], ["Group", s["group"] or "-"],
                   ["Roll", s["roll"] or "-"], ["Mobile", s["mobile"] or "-"], ["Address", s["address"] or "-"],
                   ["Academic Year", d["school"]["academic_year"]]], [45 * mm, 110 * mm])
    t.wrapOn(c, w, h)
    t.drawOn(c, 20 * mm, h - 125 * mm)
    c.drawImage(_qr(d["qr_payload"]), w - 45 * mm, h - 80 * mm, 25 * mm, 25 * mm)
    c.line(w - 75 * mm, 30 * mm, w - 20 * mm, 30 * mm)
    c.setFont("Helvetica", 9)
    c.drawString(w - 75 * mm, 25 * mm, f'Head Master: {d["school"]["headmaster"]}')
    c.save()
    return buf.getvalue()


def _testimonial(d):
    buf = io.BytesIO()
    w, h = A4
    c = canvas.Canvas(buf, pagesize=A4)
    _letterhead(c, d, w, h - 10 * mm)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(w / 2, h - 50 * mm, "TESTIMONIAL / CHARACTER CERTIFICATE")
    s, p = d["student"], d["pronoun"]
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontSize = 12
    body.leading = 20
    text = (f'This is to certify that <b>{s["name"]}</b>, {p["child"]} of <b>{s["father_name"] or "..........."}</b> '
            f'and <b>{s["mother_name"] or "..........."}</b>, bearing Student ID <b>{s["student_id"]}</b>, is a bona fide '
            f'student of Class <b>{s["class"]}</b> of this institution'
            + (f', born on <b>{s["dob"]}</b>' if s["dob"] else "") +
            f'. To the best of my knowledge, {p["subject"]} bears a good moral character and has not been involved in any '
            f'activity subversive of discipline. I wish {p["possessive"]} every success in life.')
    para = Paragraph(text, body)
    pw, ph = para.wrap(w - 50 * mm, h)
    para.drawOn(c, 25 * mm, h - 75 * mm - ph)
    c.setFont("Helvetica", 10)
    c.drawString(25 * mm, 60 * mm, f'Date: {d["issued_on"]}')
    c.line(w - 80 * mm, 60 * mm, w - 25 * mm, 60 * mm)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(w - 80 * mm, 55 * mm, d["school"]["headmaster"])
    c.setFont("Helvetica", 10)
    c.drawString(w - 80 * mm, 50 * mm, "Head Master")
    c.drawString(w - 80 * mm, 45 * mm, d["school"]["name"])
    c.save()
    return buf.getvalue()


def _report_card(d):
    buf = io.BytesIO()
    w, h = A4
    # grading scale box is drawn top-right on every page
    def page_decor(c, doc):
        c.saveState()
        _letterhead(c, d, w, h - 8 * mm)
        scale = d["result"]["grading_scale"]
        x, y = w - 52 * mm, h - 62 * mm
        c.setFont("Helvetica-Bold", 6.5)
        c.drawString(x, y + 21 * mm, "GRADING SCALE")
        c.setFont("Helvetica", 6.5)
        for i, r in enumerate(scale):
            c.drawString(x, y + 17 * mm - i * 2.7 * mm, f'{r["range"]}%   {r["grade"]}   GP {r["gp"]:.2f}')
        c.rect(x - 2 * mm, y - 3 * mm, 50 * mm, 27 * mm)
        c.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=70 * mm,
                            bottomMargin=20 * mm)
    st = getSampleStyleSheet()
    r, s = d["result"], d["student"]
    story = [Paragraph(f'<b>RESULT SHEET - {d["exam"]["name"].upper()} {d["exam"]["academic_year"]}</b>', st["Heading3"])]
    story.append(_kv_table([["Name", s["name"], "Student ID", s["student_id"]],
                            ["Class", s["class"], "Section / Roll", f'{s["section"] or "-"} / {s["roll"] or "-"}'],
                            ["Group", s["group"] or "-", "Father", s["father_name"] or "-"]],
                           [22 * mm, 65 * mm, 28 * mm, 65 * mm]))
    story.append(Spacer(1, 4 * mm))
    head = ["Subject", "Code", "CQ", "Short", "MCQ", "Prac.", "CA", "Total", "Grade", "GP"]
    data = [head]
    spans = []
    for row in r["subjects"]:
        fmt = lambda v, mx: "-" if not mx else ("AB" if row["absent"] else f"{v:g}")
        data.append([row["subject"] + (" (4th)" if row["is_fourth"] else ""), row["code"],
                     fmt(row["cq"], row["distribution"]["cq"]), fmt(row["short"], row["distribution"]["short"]),
                     fmt(row["mcq"], row["distribution"]["mcq"]), fmt(row["practical"], row["distribution"]["practical"]),
                     f'{row.get("continuous_assessment",0)+row.get("viva",0)+row.get("assignment",0):g}',
                     f'{row["total"]:g}/{row["max"]}', row["grade"], f'{row["gp"]:.2f}'])
    t = Table(data, colWidths=[48 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm, 22 * mm, 12 * mm, 12 * mm],
              repeatRows=1)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), NAVY),
             ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8),
             ("ALIGN", (1, 0), (-1, -1), "CENTER")]
    for i, row in enumerate(r["subjects"], 1):
        if not row["passed"]:
            style.append(("TEXTCOLOR", (8, i), (9, i), colors.red))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 5 * mm))
    story.append(_kv_table([["Total Marks", f'{r["grand_total"]:g} / {r["full_marks"]}', "GPA", f'{r["gpa"]:.2f}'],
                            ["Letter Grade", r["grade"], "Result", r["status"]],
                            ["Merit Position", str(d.get("merit_position") or "-"), "Pass Mark", f'{r["exam"]["pass_mark"]}%']],
                           [32 * mm, 55 * mm, 28 * mm, 55 * mm]))
    if r["failed_subjects"]:
        story.append(Paragraph(f'Failed in: {", ".join(r["failed_subjects"])}', st["Normal"]))
    doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    return buf.getvalue()


RENDERERS = {"id-card": _id_card, "staff-id-card": _id_card, "admit-card": _admit_card,
             "registration-card": _registration_card, "testimonial": _testimonial, "report-card": _report_card}


def render_pdf(data):
    return RENDERERS[data["kind"]](data)


def id_cards_pdf(students):
    """Create a batch PDF with one student card per page."""
    config = SchoolConfig.get()
    buf = io.BytesIO()
    w, h = 85.6 * mm, 54 * mm
    c = canvas.Canvas(buf, pagesize=(w, h))
    for student in students:
        data = {"school": school_info(config), "student": student_brief(student),
                "qr_payload": f"{student.student_id}|{student.name}|{student.school_class.name}"}
        c.setFillColor(NAVY); c.rect(0, h - 12 * mm, w, 12 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(w / 2, h - 6 * mm, data["school"]["name"])
        c.setFont("Helvetica", 6); c.drawCentredString(w / 2, h - 10 * mm, f'{data["school"]["location"]} | EIN {data["school"]["ein"]}')
        s = data["student"]; c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 7)
        c.drawString(5 * mm, h - 17 * mm, "STUDENT ID CARD")
        y = h - 23 * mm
        lines = [("Name", s["name"]), ("ID", s["student_id"]),
                 ("Class", f'{s["class"]} {s["section"] or ""} {("(" + s["group"] + ")") if s["group"] else ""}'),
                 ("Roll", s["roll"] or "-"), ("Mobile", s["mobile"] or "-")]
        for key, value in lines:
            c.setFont("Helvetica-Bold", 7); c.drawString(5 * mm, y, f"{key}:")
            c.setFont("Helvetica", 7); c.drawString(20 * mm, y, str(value)[:55]); y -= 4.5 * mm
        c.drawImage(_qr(data["qr_payload"]), w - 22 * mm, 6 * mm, 17 * mm, 17 * mm)
        c.setFont("Helvetica", 5.5); c.drawString(5 * mm, 3 * mm, f'Valid for academic year {data["school"]["academic_year"]}')
        c.showPage()
    c.save()
    return buf.getvalue()
