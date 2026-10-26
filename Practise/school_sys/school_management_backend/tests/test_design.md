# Manual acceptance test checklist

- [ ] `GET /api/v1/health/` works without authentication.
- [ ] Login as `admin` and `headmaster` succeeds; ordinary authenticated users cannot mutate.
- [ ] Create classes and sections; create/update/delete student.
- [ ] A student's section must belong to their selected class.
- [ ] Deleting a populated section without `move_to_section` fails safely.
- [ ] Deleting a populated section with a valid same-class `move_to_section` moves students and deletes the section.
- [ ] Bulk create students is atomic; invalid rows fail validation.
- [ ] Import CSV/XLSX students and inspect row-level errors.
- [ ] Configure only the desired subjects on an exam and set pass thresholds.
- [ ] Enter one result below a component threshold; it grades F even if the total is high.
- [ ] Export student/result CSV, XLSX, DOCX, and PDF.
- [ ] Generate ID, registration, transfer and testimonial PDFs.
- [ ] Verify every seed-generated result is marked `is_synthetic=true`.
