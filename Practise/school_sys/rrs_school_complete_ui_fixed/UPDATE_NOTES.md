# UI correction update

This update specifically addresses the reported usability issues:

- Marks use a spreadsheet-style grid with sticky headers, row numbers, compact editable cells, and a live row total. Mark values can be entered directly in the table; save/import/export actions remain available.
- Results load automatically when the Results page opens, using the latest available examination by default. Class and academic-year filters default to that latest exam, and can be changed before reloading results.
- Documents/PDFs use human-readable student/teacher dropdowns. Selecting a person immediately loads the preview with the person's name, student ID, class, section, roll, and other available details. Document type and exam changes refresh relevant previews; report/admit cards require an examination selection.
- Student editing filters section choices to the selected class. Section CRUD and safe merge-before-delete behavior remain available from the Sections menu.
- Existing uploaded student and marks CSVs are included in `data/` where available; use `uv run python manage.py import_school_data` to import them.

Validation: JavaScript syntax (`node --check`) and Python compilation (`compileall`) passed. A Django runtime check could not run in this environment because Django is not installed in the local virtual environment; install dependencies with `uv sync` first.
