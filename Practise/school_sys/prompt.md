You are an expert Django Architect and Senior Full-Stack Engineer. Your task is to build a modern, clean, modular, and highly maintainable School Management System backend and administration web app for **RRS High School H20** (EIN: 12187, Estd: 2022, Location: Cox's Bazar) using Python and the **`uv`** package manager.

The codebase must strictly follow Django best practices, DRY (Don't Repeat Yourself) principles, clean service layers, and clean URL structuring, making it easy to extend, update, and maintain.

---

### 1. Technology Stack & Environment
* **Language:** Python
* **Framework:** Django
* **Package Manager:** `uv`
* **Database:** SQLite (default for easy setup, with clean Django ORM models).
* **PDF/Document Generation:**  (for generating ID cards, admit cards, registration cards, testimonials, and report cards).
* **Import/Export:**  for Excel/CSV bulk operations.

---

### 2. Core Functional Requirements

#### A. School Configuration & Dynamic Settings (Singleton/Config Model)
* **School Name:** RRS High School H20
* **EIN:** 12187
* **Estd:** 2022
* **Location:** Cox's Bazar
* **Configurable Attributes:** School logo, address, contact info, current academic year, grading scale boundaries, default pass marks, class periods duration, and routine settings.

#### B. Authentication & Role-Based Access Control (RBAC)
* **Roles:** Super Admin, Headmaster, Teacher, Student/Staff.
* **Seed Data Credentials (`management/commands/seed_data.py`):**
  * **Super Admin:** `admin123`
  * **Headmaster / Admin Staff:** `password123`
  * **Teacher Accounts:** `teacher123` (for teachers: Md. Shahjahan Khan [Head Master], Taohidul Islam [Computer Operator], Ajkar Uddin Sikdar, Md. Khalis Miah, Mitun Debnath, Suma Begum, Md. Maynul Islam, Nusrot Jahan Mohim, Rujyna Akther, Rafiur Rahman Saikat).

#### C. Full NCTB Subjects, Codes & Marks Master List
The system must support and seed the following complete subject directory:

| SL | Subject Name (English / Bangla) | Subject Code | Total Marks |
|---|---|---|---|
| 1 | Bangla 1st Paper (বাংলা ১ম পত্র) | 101 | 100 |
| 2 | Bangla 2nd Paper (বাংলা ২য় পত্র) | 102 | 100 |
| 3 | English 1st Paper (ইংরেজি ১ম পত্র) | 107 | 100 |
| 4 | English 2nd Paper (ইংরেজি ২য় পত্র) | 108 | 100 |
| 5 | Mathematics (গণিত) | 109 | 100 |
| 6 | Information and Communication Technology (তথ্য ও যোগাযোগ প্রযুক্তি) | 154 | 50 |
| 7 | Chemistry (রসায়ন) | 137 | 100 |
| 8 | Higher Mathematics (উচ্চতর গণিত) | 126 | 100 |
| 9 | Physics (পদার্থবিজ্ঞান) | 136 | 100 |
| 10 | Biology (জীববিজ্ঞান) | 138 | 100 |
| 11 | Bangladesh and Global Studies (বাংলাদেশ ও বিশ্বপরিচয়) | 150 | 100 |
| 12 | General Science (বিজ্ঞান / সাধারণ বিজ্ঞান) | 127 | 100 |
| 13 | Economics (অর্থনীতি) | 141 | 100 |
| 14 | Civics and Citizenship (পৌরনীতি ও নাগরিকতা) | 140 | 100 |
| 15 | History of Bangladesh and World Civilization (বাংলাদেশের ইতিহাস ও বিশ্বসভ্যতা) | 153 | 100 |
| 16 | Geography and Environment (ভূগোল ও পরিবেশ) | 110 | 100 |
| 17 | Accounting (হিসাববিজ্ঞান) | 146 | 100 |
| 18 | Business Entrepreneurship (ব্যবসায় উদ্যোগ) | 143 | 100 |
| 19 | Finance and Banking (ফিন্যান্স ও ব্যাংকিং) | 152 | 100 |
| 20 | Agriculture Studies (কৃষিশিক্ষা) | 134 | 100 |
| 21 | Home Science (গার্হস্থ্য বিজ্ঞান) | 151 | 100 |
| 22 | Fine Arts & Crafts (চারু ও কারুকলা) | 148 | 100 |
| 23 | Career Education (ক্যারিয়ার শিক্ষা) | 156 | 50 |
| 24 | Physical Education, Health Science & Sports (শারীরিক শিক্ষা, স্বাস্থ্যবিজ্ঞান ও খেলাধুলা) | 147 | 50 |
| 25 | Islam and Moral Education (ইসলাম শিক্ষা / ইসলাম ও নৈতিক শিক্ষা) | 111 | 100 |
| 26 | Hindu Religion and Moral Education (হিন্দুধর্ম শিক্ষা) | 112 | 100 |
| 27 | Christian Religion and Moral Education (খ্রিস্টধর্ম শিক্ষা) | 114 | 100 |
| 28 | Buddhist Religion and Moral Education (বৌদ্ধধর্ম শিক্ষা) | 113 | 100 |
| 29 | Arabic (আরবি) | 121 | 100 |
| 30 | Sanskrit (সংস্কৃত) | 123 | 100 |
| 31 | Pali (পালি) | 124 | 100 |
| 32 | Music (সঙ্গীত) | 149 | 100 |

#### D. Marks Evaluation Rules & Grading Scale Matrix
1. **Practical Subjects (Physics 136, Chemistry 137, Biology 138, Higher Math 126, Agriculture 134, Home Science 151, Music 149, etc.):**
   * Theoretical: CQ (40) + Short (10) + MCQ (25) = 75 Marks
   * Practical: 25 Marks
   * Component Pass Thresholds: CQ $\ge$ 13/40, MCQ $\ge$ 8/25, Practical $\ge$ 8/25. Failure in any single part results in an overall 'F'.
2. **General Written Subjects (Bangla 101, Math 109, BGS 150, Religion, Humanities, Business Studies, etc.):**
   * Written (CQ 50 + Short 20 = 70 Marks) + MCQ (30 Marks)
   * Component Pass Thresholds: Written $\ge$ 23/70, MCQ $\ge$ 10/30.
3. **50-Mark Subjects (ICT 154, Career Education 156, Physical Education 147):**
   * ICT (154): MCQ (25 Marks, Pass $\ge$ 8) + Practical (25 Marks, Pass $\ge$ 8).
   * Career / Physical Ed: Follow appropriate scaled pass targets ($\ge$ 33% overall and component-wise).
4. **Combined Pass Rules:**
   * Bangla 1st Paper (101) + 2nd Paper (102) combined total $\ge$ 66/200.
   * English 1st Paper (107) + 2nd Paper (108) combined total $\ge$ 66/200.
5. **Grading Scale Matrix:**
   * 80% – 100% = **A+** (5.00 GP)
   * 70% – 79%   = **A**  (4.00 GP)
   * 60% – 69%   = **A-** (3.50 GP)
   * 50% – 59%   = **B**  (3.00 GP)
   * 40% – 49%   = **C**  (2.00 GP)
   * 33% – 39%   = **D**  (1.00 GP)
   * 00% – 32%   = **F**  (0.00 GP - Fail). Any mandatory subject with 'F' forces the final result status to "Failed".

#### E. Student Management & Bulk Operations
* Full CRUD for Students, Teachers, Classes (Six to Ten), and Sections (A, B, etc.).
* **Bulk Import/Export:** CSV and Excel upload/download views for student profiles and marks entries.
* Include seed student records provided in prompt data (Nusrat Jannat, Kazi Tanjina Begum, Esrar Jannat Nuhi, Marjana Begum, Sanjida Begum Mili, Mst Sadia Begum, Tahmina Akter Tamanna, etc.) with correct DOBs, mobile numbers, and addresses.

#### F. Automated Result Engine & Card Generation (PDF)
* Automated result computation service implementing all NCTB combined/individual pass rules and GPA scaling.
* PDF Card Generation for:
  1. Student & Staff ID Cards (with QR/Barcode mockup)
  2. Admit Cards
  3. Registration Cards
  4. Character Certificates / Testimonials (signed by Head Master Md. Shahjahan Khan)
  5. Result Sheets / Report Cards (detailed breakdown with GPA & marks distribution)

---

### 3. Output Deliverables
Please generate:
1. `pyproject.toml` formatted for `uv`.
2. Clean Django project directory structure.
3. Python models, views, services, and result calculation logic.
4. Custom Django management command  to seed school metadata, all 32 NCTB subjects, default user accounts, teachers, and sample students.
5. Complete `README.md` with step-by-step instructions for `uv` environment initialization, migration, data seeding, and running the app.