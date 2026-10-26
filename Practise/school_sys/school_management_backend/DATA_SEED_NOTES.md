# Seed data notes

- `data/students_source.csv` is the source roster supplied for this project (307 CSV data rows, spanning classes 6–10).
- Run `python manage.py seed_school` after migrations to import/update the roster and create users, classes, sections, subjects, exam configurations, and synthetic results.
- Since the source roster has no student group field, the command assigns Science/Humanities deterministically for demo purposes in classes 9–10; classes 6–8 are assigned Humanities. This is placeholder data and must be reviewed before use.
- All generated marks are fabricated and stored with `is_synthetic=true`. The command generates demo marks for 2025 Annual, 2025 Half Yearly, and 2027 Half Yearly only. Class 10's 2027 Pre Test, Model Test, and Test exams are created without marks.
- Seeded login credentials are `admin / password123` and `headmaster / password123`. Development only; change them before deployment.
- Some source rows have missing or malformed dates/phones and duplicate rolls/names. Review records after import.
