# RRS High School H20 — Django backend + frontend

## Requirements
- Python 3.12+
- `uv` package manager

## Setup
```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed_data
uv run python manage.py runserver
```
Open frontend: http://127.0.0.1:8000/
Django admin: http://127.0.0.1:8000/admin/
API root: http://127.0.0.1:8000/api/

## Seed credentials (local development only)
- Super admin: `admin` / `admin123`
- Headmaster: `headmaster` / `password123`
- Teacher accounts: see `school/management/commands/seed_data.py`, password `teacher123`.

Change development passwords and `DJANGO_SECRET_KEY` before deployment. Do not expose this development server publicly.

## Postman
Import both files from `postman/`:
- `RRS_High_School_API.postman_collection.json`
- `RRS_School_Local.postman_environment.json`
Select **RRS School — Local** environment, then run **Authentication → Login — admin**. The token is saved to `token` and reused by the collection. Update `student_id`, `exam_id`, `subject_id`, and other ID variables to match your seeded database. CRUD sample payloads may need foreign-key IDs that already exist.

## Frontend features
- Login with DRF token authentication
- Dashboard summary and school configuration
- CRUD for students, teachers, classes, groups, sections, subjects and exams
- Academic-session dropdown persisted to school configuration
- Human-readable dropdowns for student class, section, group and optional subject assignment
- Marks bulk entry with inline spreadsheet-style grid and CSV/XLSX/JSON import support
- Latest-exam-first result table with class/year/gender/name/roll/section/group filters, plus detailed transcript view
- Human-readable document preview with raw JSON available in a collapsible panel; PDF opening and batch ID-card printing
- School config editing

## API endpoint overview
- `POST /api/auth/login/`, `GET /api/auth/me/`
- CRUD `/api/classes/`, `/api/groups/`, `/api/sections/`, `/api/teachers/`, `/api/subjects/`, `/api/class-subjects/`, `/api/students/`, `/api/exams/`, `/api/marks/`
- `GET/PATCH /api/config/`
- `GET /api/results/?student=<id>&exam=<id>` returns one detailed transcript; without `student`, it returns class-wide results for the selected/latest matching exam. Filters include `school_class`, `academic_year`, `gender`, `name`, `roll`, `section`, and `group`.
- `GET /api/exams/<id>/results/`
- `POST /api/marks/bulk/` and `GET /api/marks/template/?exam=<id>&subject=<id>&file_type=csv|xlsx|json` (optional `section` and `group` filters)
- Student and mark imports support CSV, XLSX and JSON through the API; the bundled `import_school_data` command additionally understands the supplied wide-format marks CSV. Import/export endpoints are listed in the Postman collection.
- Document endpoints: `/api/documents/<kind>/<id>/?output=json|pdf`; kinds: `id-card`, `staff-id-card`, `admit-card`, `registration-card`, `testimonial`, `report-card`.

## Notes
- The academic-session selector updates `SchoolConfig.current_academic_year`; exam-specific filters remain available for historical sessions.
- The system is configured for one institution (RRS High School H20); whole-school batch printing covers all active students in that configured school.
- SQLite is the default database.
- The UI uses Django templates and vanilla JavaScript/CSS, no Node build step.
- Student and exam APIs require valid related database IDs.
- `seed_data` only includes the student details available to the existing project; add any missing student DOB/mobile/address details when you have the source list.

## Load the supplied 2026 CSV files

After migrations, run the bundled CSV loader (the uploaded CSVs are included in `data/`):

```bash
uv run python manage.py import_school_data
```

To supply different files, pass `--students /path/to/students.csv --marks /path/to/marks.csv`. Add `--skip-history` to omit generated historical exams. The loader seeds the curriculum, normalizes class names and Excel-style phone values, creates missing sections, imports/updates the student register, creates exam history for 2025 First Term, Mid Term and Final Exam plus 2026 First Term, Mid Term and Half-Yearly for Classes 6–10, and overlays the supplied wide-format marks onto matching Class Ten students in the 2026 Half-Yearly exam. Generated history marks are synthetic demo values; uploaded marks are the supplied values. The marks file contains a few rows with extra trailing empty columns; the importer tolerates them.

## Added academic endpoints

- `GET /api/academic-context/?school_class=<id>` or `?exam=<id>` loads students, enabled subjects and mark distributions for dynamic forms.
- `POST /api/students/promote/` accepts `student_ids`, `target_class`, `academic_year`, optional `section`/`group`; include `exam` to move only students who passed that exam. Without `target_class`, a non-terminal exam can auto-promote to the next class.
- `GET /api/documents/id-cards/?output=json|pdf` supports whole-school batches and optional `school_class`, `section`, `group`, or `student` filters.
- `GET/POST/PATCH/DELETE /api/class-groups/` controls group enablement per class; `/api/class-subjects/` toggles curriculum subjects per class/group.
- Exam records now accept `component_distribution`, `grading_scale`, `pass_mark`, and `require_component_pass`. Mark records support CQ, short, MCQ, practical, continuous assessment, viva and assignment.
- Student ID formats are configurable in School settings with tokens `{Session}`, `{Year}`, `{Class}`, `{ClassCode}`, `{Section}`, `{Group}`, `{GroupCode}`, `{Roll}`, and `{ID}`.
- Student and mark imports accept CSV, XLSX and JSON files; mark templates and exports can be generated as CSV, XLSX or JSON.
