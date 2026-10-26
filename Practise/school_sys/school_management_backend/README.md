# School Management Backend (Django REST Framework)

A modular, API-first backend for a Bangladesh secondary school. Includes classes, sections, student CRUD/bulk import-export, configurable exams and subjects, component-aware grading, synthetic demo results, JWT authentication and PDF student cards.

> **Important data note:** the supplied CSV has student names, family details, dates of birth, phone numbers and addresses. Treat this as sensitive student data. The seed command imports the provided records into your local database. Demo results are fabricated and flagged `is_synthetic=true`; they are not official academic records. The seed command assigns Science/Humanities deterministically for demo purposes because the CSV has no group column. Review every assignment before real use.

## Stack / structure

- Django 5.x, Django REST Framework, SimpleJWT, django-filter
- SQLite for local development; switch `DATABASES` to PostgreSQL for production.
- `apps/academics`: class and section entities
- `apps/students`: student profiles, bulk create, CSV import/export, CSV/XLSX/PDF export
- `apps/exams`: subjects, per-exam subject configuration, marks, grade calculation, result export
- `apps/documents`: generated PDF ID/administration/registration/transfer/testimonial documents
- `apps/core`: permissions, health check, seed command

The code avoids a large service layer for trivial CRUD, but puts student-section integrity in model/serializer validation and section deletion in a transaction. Section deletion refuses to proceed when students remain unless a same-class destination section is supplied.

## Quick start

Python 3.11+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # optional; edit SECRET_KEY for deployment
python manage.py makemigrations academics students exams
python manage.py migrate
python manage.py seed_school
python manage.py runserver
```

API base: `http://127.0.0.1:8000/api/v1/`
Admin UI: `http://127.0.0.1:8000/admin/`

The seed command reads `data/students_source.csv`. To point at another file:

```bash
python manage.py seed_school --csv /absolute/path/to/students.csv
```

Seed accounts (development only):

- `admin` / `password123` (Admin group)
- `headmaster` / `password123` (Headmaster group)

Both are staff users and can mutate school data. Replace these passwords and the Django secret before deployment. Do not expose a seeded development account publicly.

## Authentication

Obtain a JWT:

```http
POST /api/v1/auth/token/
Content-Type: application/json

{"username":"admin","password":"password123"}
```

Use the response's `access` value as `Authorization: Bearer <access>`. Refresh with `POST /api/v1/auth/token/refresh/` and `{"refresh":"..."}`.

All API routes except `/api/v1/health/` and token acquisition require authentication. Read access is allowed to any authenticated user; mutations are restricted to superusers or members of the `Admin` / `Headmaster` groups. In a production school, narrow read permissions to roles and class assignments as appropriate.

## Main endpoints

| Feature                  | Endpoint                                                                                                |
| ------------------------ | ------------------------------------------------------------------------------------------------------- |
| Health                   | `GET /api/v1/health/`                                                                                   |
| Classes CRUD             | `/api/v1/classes/`                                                                                      |
| Sections CRUD            | `/api/v1/sections/`                                                                                     |
| Students CRUD            | `/api/v1/students/`                                                                                     |
| Bulk create students     | `POST /api/v1/students/bulk/` with `{"students":[...]}`                                                 |
| Import students CSV/XLSX | `POST /api/v1/students/import-file/` multipart field `file`                                             |
| Export students          | `GET /api/v1/students/export-file/?format=csv                                                           |
| Subjects CRUD            | `/api/v1/subjects/`                                                                                     |
| Exams CRUD               | `/api/v1/exams/`                                                                                        |
| Configure exam subjects  | `POST /api/v1/exams/{id}/configure-subjects/`                                                           |
| Results CRUD             | `/api/v1/results/`                                                                                      |
| Bulk result upsert       | `POST /api/v1/results/bulk/`                                                                            |
| Import results CSV/XLSX  | `POST /api/v1/results/import-file/` multipart CSV/XLSX (`student_id`, `exam_subject_id`, marks columns) |
| Export results           | `GET /api/v1/results/export-file/?format=csv                                                            |
| Generate student card    | `GET /api/v1/students/{id}/card/?kind=ID`                                                               |

Use standard DRF filters, e.g. `/api/v1/students/?school_class=4&section=7&search=SAIMA`, `/api/v1/results/?exam_subject__exam=3`, or `/api/v1/students/export-file/?format=xlsx&school_class=4`.

### Student create example

```json
{
  "roll": 1,
  "name": "Example Student",
  "father_name": "Example Father",
  "mother_name": "Example Mother",
  "school_class": 1,
  "section": 1,
  "group": "HUMANITIES",
  "date_of_birth": "2012-01-15",
  "phone": "01700000000",
  "address": "Sylhet"
}
```

`admission_no` is generated when omitted. `school_class` and `section` must refer to the same class.

### Section removal / student reassignment

If a section is empty, `DELETE /api/v1/sections/{id}/` deletes it. If it contains students, the API returns a validation error and requires a destination:
`DELETE /api/v1/sections/{id}/?move_to_section=12`
The destination must be another section in the same class. Students are moved transactionally before deletion. This avoids accidental orphaning or silent student loss. If the last section is being removed, create another section first.

### Exam configuration / pass marks

Create an exam with `name`, `academic_year`, `kind`, and class IDs, then call `configure-subjects`. Only subjects included in this exam will be graded. Example:

```json
{
  "mode": "replace",
  "subjects": [
    {
      "subject": 1,
      "total_marks": 100,
      "cq_max": 50,
      "short_max": 20,
      "mcq_max": 30,
      "practical_max": 0,
      "pass_marks": 33,
      "written_pass_marks": 23,
      "mcq_pass_marks": 10,
      "practical_pass_marks": 0
    },
    {
      "subject": 6,
      "total_marks": 50,
      "cq_max": 0,
      "short_max": 0,
      "mcq_max": 25,
      "practical_max": 25,
      "pass_marks": 17,
      "cq_pass_marks": 0,
      "mcq_pass_marks": 8,
      "practical_pass_marks": 8
    }
  ]
}
```

Use `mode: "merge"` to update/add selected subjects without removing existing ones, or `mode: "replace"` to make the exam contain exactly the supplied subject list. Replace refuses to delete existing results unless `delete_existing_results: true` is explicitly supplied. For component gates, use `0` to disable that component's independent threshold. `written_pass_marks` checks CQ + short answer together for general subjects; science practical subjects can use separate CQ, MCQ and practical gates. Current grading uses the configured component thresholds and a minimum 33% overall for passing. It applies the familiar Bangladesh scale: A+ 80%/5.00, A 70%/4.00, A- 60%/3.50, B 50%/3.00, C 40%/2.00, D 33%/1.00, otherwise F/0.00. Bangla 1st+2nd and English 1st+2nd are additionally failed as a pair when their combined result is below 66/200. Individual paper grades remain based on their configured per-paper grading. Validate these rules against the applicable board circular before official use.

Exam types are configurable via the `Exam.Kind` choices. Seeded sample setup:

- Classes 6–9: Half Yearly and Annual (2025 demo records; 2027 Half Yearly demo records)
- Class 10: Half Yearly, Pre Test, Model Test and Test exam configurations for 2027; demo marks are generated only for 2025 Annual, 2025 Half Yearly and the already-conducted 2027 Half Yearly.

The source subject list you provided is used as seed catalog, but subject availability can vary by class and board curriculum. Subject/component thresholds are configurable per exam subject. Result writes validate that marks do not exceed the configured component maxima. Religion subject is not inferred from student records, so review/assign the appropriate religion subject manually. Business Studies is in the subject catalog but no business students are created by the seed command.

## Cards and documents

`GET /api/v1/students/{id}/card/?kind=ID` returns a generated PDF. Supported `kind` values: `ID`, `ADMINISTRATION`, `REGISTRATION`, `TRANSFER`, `TESTIMONIAL`. These are printable templates, not board-issued certificates. Add your school's real name, logo, EIIN, signatures, Bengali-capable fonts and approval workflow before issuing official documents. The current PDF uses standard Helvetica and may not render Bangla text correctly.

## Import source and data cleanup

The source CSV is preserved at `data/students_source.csv`. Some records contain malformed or placeholder birth dates, Excel-formula-wrapped phone numbers, repeated names/rolls and missing fields. Invalid placeholder dates are imported as blank. The seed command does not overwrite existing students with matching name/class/section/roll and is safe to re-run for demo setup, but review duplicate identities manually.

## Export / backups

- Students and results support CSV, XLSX, DOCX, and PDF exports. Students and results import CSV/XLSX files.
- Result file import expects `student_id`, `exam_subject_id`, `cq_marks`, `short_marks`, `mcq_marks`, `practical_marks`, and optionally `is_synthetic`. It reports row-level errors; validate before committing official marks.
- Back up `db.sqlite3` and `media/`. Do not store production credentials in source control.

## Testing

```bash
python manage.py check
python manage.py test
```

Import `postman/School_Management_API.postman_collection.json` and `postman/School_Management_API.postman_environment.json` into Postman. Set `base_url` to your server, request a token, then use the `access_token` environment variable.

## Production checklist

1. Use PostgreSQL, HTTPS, secure `SECRET_KEY`, `DEBUG=False`, restricted `ALLOWED_HOSTS`, secure cookies and proper CORS/CSRF policy.
2. Replace seeded credentials immediately; enforce password policy and backups.
3. Add audit logs for marks, student edits, section moves and document issuance.
4. Add granular role permissions, pagination limits, rate limiting and object-level access rules.
5. Validate official NCTB/education-board subject and grading circulars; demo grades are synthetic and must not be used as official results.
