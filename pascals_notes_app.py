# pascals_notes_app.py
"""
Pascal'sNotes - updated to support single or multiple file uploads

What's changed:
- Upload form (user) accepts multiple files at once (input name 'files', multiple attribute)
- Admin upload form accepts multiple files too
- Server handles request.files.getlist('files') and processes each PDF separately
- Database entries created per file (subject + grade preserved)
- Flash summary shows how many files were accepted / rejected
- All other behaviour unchanged
"""
from flask import Flask, request, redirect, url_for, render_template_string, send_from_directory, flash, session
from werkzeug.utils import secure_filename
import os
import sqlite3
from datetime import datetime
import hashlib

# ----------------------
# Configuration
# ----------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(APP_DIR, 'storage')
PENDING_DIR = os.path.join(STORAGE_DIR, 'pending')
APPROVED_DIR = os.path.join(STORAGE_DIR, 'approved')
DB_PATH = os.path.join(APP_DIR, 'pascals_notes.db')
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB per request (adjust if needed)

# Admin password (default replaced per your request)
ADMIN_PASSWORD = os.environ.get('PASCAL_ADMIN_PASSWORD', 'Paa@Len0181003@@#*$')
SECRET_KEY = os.environ.get('PASCAL_SECRET_KEY', hashlib.sha256(b"pascalsnotes_secret").hexdigest())

# ----------------------
# Subjects with grade support
# ----------------------
SUBJECTS = {
    'Mathematics': ['8','9','10','11','12'],
    'Mathematical Literacy': ['10','11','12'],
    'Physical Sciences': ['10','11','12'],
    'Life Sciences': ['10','11','12'],
    'Accounting': ['10','11','12'],
    'Geography': ['10','11','12'],
    'Economics': ['10','11','12'],
    'Business Studies': ['10','11','12'],
    'Agricultural Sciences': ['10','11','12'],
    'EMS': ['8','9'],
    'Natural Sciences': ['8','9'],
}

# ----------------------
# Ensure directories and DB
# ----------------------
os.makedirs(PENDING_DIR, exist_ok=True)
os.makedirs(APPROVED_DIR, exist_ok=True)

# ----------------------
# Database helpers
# ----------------------
def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT,
            subject TEXT,
            grade TEXT,
            uploader TEXT,
            status TEXT NOT NULL,
            notes TEXT,
            uploaded_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

# In case user has an older DB without grade column, ensure column exists
def ensure_grade_column():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("PRAGMA table_info(uploads)")
    cols = [r['name'] for r in c.fetchall()]
    if 'grade' not in cols:
        c.execute('ALTER TABLE uploads ADD COLUMN grade TEXT')
        conn.commit()
    conn.close()

init_db()
ensure_grade_column()

# ----------------------
# Flask app
# ----------------------
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.secret_key = SECRET_KEY

# ----------------------
# Utility
# ----------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file_storage, subdir=PENDING_DIR):
    original = file_storage.filename
    filename = secure_filename(original)
    # make filename unique with timestamp
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    filename = f"{timestamp}__{filename}"
    path = os.path.join(subdir, filename)
    file_storage.save(path)
    return filename, original

# ----------------------
# Templates (render_template_string)
# ----------------------
BASE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pascal'sNotes</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    :root{
      --accent:#0b5ed7;
      --brand-dark:#08203a;
      --muted:#6c757d;
      --card-bg:#ffffff;
      --bg:#f4f7fb;
      --glass: rgba(255,255,255,0.75);
    }
    body{background:var(--bg);padding-top:5.2rem;padding-bottom:96px;color:#222}
    .navbar-brand{font-weight:700}
    .hero{background:linear-gradient(90deg, rgba(13,110,253,0.06), rgba(13,110,253,0.03));padding:2rem;border-radius:.6rem}
    .subject-card{border:0;border-radius:.6rem;box-shadow:0 6px 18px rgba(34,45,60,0.06);}
    .subject-card:hover{transform:translateY(-4px);transition:all .18s ease}
    .grade-badge{margin-right:.25rem}
    .small-note{color:var(--muted);font-size:.92rem}
    .file-actions a{margin-left:.35rem}
    footer{padding:2.5rem 0;color:var(--muted)}
    .filter-row .form-control{min-width:160px}
    @media (max-width:576px){ .subject-card{min-height:140px} }
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-white bg-white fixed-top shadow-sm">
  <div class="container">
    <a class="navbar-brand" href="{{ url_for('index') }}">Pascal'sNotes</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#nav" aria-controls="nav" aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon">☰</span>
    </button>
    <div class="collapse navbar-collapse" id="nav">
      <ul class="navbar-nav ms-auto">
        <li class="nav-item"><a class="nav-link" href="{{ url_for('browse') }}">All Notes</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('upload') }}">Upload Notes</a></li>
      </ul>
    </div>
  </div>
</nav>

<div class="container mt-4">
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <div class="mt-2">
        {% for m in messages %}
          <div class="alert alert-info">{{ m }}</div>
        {% endfor %}
      </div>
    {% endif %}
  {% endwith %}
  {% block content %}{% endblock %}
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

INDEX = """
<div class="row mb-4">
  <div class="col-md-8">
    <div class="hero">
      <h1 class="mb-1">Subjects we cover</h1>
      <p class="small-note mb-0">Study notes for Grades 8–12. Click a subject to browse approved files.</p>
    </div>
  </div>
  <div class="col-md-4 text-md-end align-self-center mt-3 mt-md-0">
    <a class="btn btn-outline-secondary" href="{{ url_for('upload') }}">Upload notes (PDF)</a>
  </div>
</div>

<div class="row">
  {% for subj, grades in subjects.items() %}
    <div class="col-md-4 mb-3">
      <div class="card subject-card p-3 h-100">
        <div class="d-flex flex-column h-100">
          <div>
            <h5 class="mb-1">{{ subj }}</h5>
            <div class="mb-2">
              {% for g in grades %}
                <span class="badge bg-light text-dark grade-badge">Grade {{ g }}</span>
              {% endfor %}
            </div>
            <p class="small-note">Notes and study material for {{ subj }} across the listed grades.</p>
          </div>
          <div class="mt-auto text-end">
            <a href="{{ url_for('browse', subject=subj) }}" class="btn btn-primary btn-sm">Browse</a>
          </div>
        </div>
      </div>
    </div>
  {% endfor %}
</div>

<footer style="position:fixed;left:0;right:0;bottom:0;background:linear-gradient(90deg,var(--accent),var(--brand-dark));color:#fff;padding:14px 0;text-align:center;box-shadow:0 -6px 24px rgba(8,32,58,0.18);">
  <div style="max-width:1100px;margin:0 auto;padding:0 16px;display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;font-size:0.95rem;">
    <div>© 2025 Pascal-Notes · All rights reserved.</div>
    <div style="opacity:0.95;">⚡ Powered by <a href="https://pascalmindtech.netlify.app/" target="_blank" style="color:rgba(255,255,255,0.95);text-decoration:underline;font-weight:600;">Pasca Ragophala</a></div>
  </div>
</footer>
"""

BROWSE = """
<div class="row mb-3 align-items-center filter-row">
  <div class="col-md-6">
    <h4>Approved notes{% if subject %} — {{ subject }}{% endif %}{% if grade %} (Grade {{ grade }}){% endif %}</h4>
    <p class="small-note mb-0">Click to view or download PDF files.</p>
  </div>
  <div class="col-md-6 text-md-end mt-3 mt-md-0">
    <form class="d-inline" method="get" action="{{ url_for('browse') }}">
      <input type="hidden" name="subject" value="{{ subject or '' }}" />
      <select name="grade" class="form-select d-inline-block" style="width:auto;" onchange="this.form.submit()">
        <option value="">All grades</option>
        {% for g in grades_available %}
          <option value="{{ g }}" {% if grade==g %}selected{% endif %}>Grade {{ g }}</option>
        {% endfor %}
      </select>
      <a class="btn btn-outline-secondary ms-2" href="{{ url_for('upload') }}">Upload</a>
    </form>
  </div>
</div>

<div class="list-group">
  {% if files|length == 0 %}
    <div class="alert alert-secondary">No approved files found.</div>
  {% else %}
    {% for f in files %}
      <div class="list-group-item d-flex justify-content-between align-items-start">
        <div>
          <div class="fw-bold">{{ f.original_name }}</div>
          <div class="small-note">Subject: {{ f.subject }} • Grade: {{ f.grade or '—' }} • Uploaded: {{ f.uploaded_at.split('T')[0] }}</div>
        </div>
        <div class="file-actions">
          <a class="btn btn-sm btn-outline-primary" href="{{ url_for('view_file', filename=f.filename) }}" target="_blank">View</a>
          <a class="btn btn-sm btn-primary" href="{{ url_for('download_file', filename=f.filename) }}">Download</a>
        </div>
      </div>
    {% endfor %}
  {% endif %}
</div>
"""

UPLOAD = """
<div class="row">
  <div class="col-md-8">
    <h3>Upload notes (PDF only)</h3>
    <form method="post" enctype="multipart/form-data">
      <div class="mb-3">
        <label class="form-label">Select subject</label>
        <select id="subject-select" name="subject" class="form-select" required onchange="populateGrades()">
          <option value="">Choose subject</option>
          {% for s in subjects.keys() %}
            <option value="{{ s }}">{{ s }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Select grade</label>
        <select id="grade-select" name="grade" class="form-select" required>
          <option value="">Choose grade</option>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Your name (optional)</label>
        <input name="uploader" class="form-control" placeholder="e.g. Thabo N." />
      </div>
      <div class="mb-3">
        <label class="form-label">File (PDF only) — you can select multiple files</label>
        <input name="files" type="file" accept="application/pdf" class="form-control" required multiple />
      </div>
      <button class="btn btn-success" type="submit">Upload (will be verified)</button>
    </form>
    <hr />
    <p class="small-note">Uploads are queued for admin verification before appearing in approved notes. No sign in required.</p>
  </div>
</div>

<script>
const SUBJECTS = {{ subjects_json|safe }};
function populateGrades(){
  const subj = document.getElementById('subject-select').value;
  const gradeSel = document.getElementById('grade-select');
  gradeSel.innerHTML = '<option value="">Choose grade</option>';
  if(!subj) return;
  const grades = SUBJECTS[subj] || [];
  grades.forEach(g=>{
    const opt = document.createElement('option');
    opt.value = g; opt.textContent = 'Grade '+g;
    gradeSel.appendChild(opt);
  });
}
</script>
"""

ADMIN_LOGIN = """
<div class="row justify-content-center">
  <div class="col-md-6">
    <h3>Admin login</h3>
    <form method="post">
      <div class="mb-3">
        <label class="form-label">Password</label>
        <input type="password" name="password" class="form-control" required />
      </div>
      <button class="btn btn-primary" type="submit">Enter</button>
    </form>
  </div>
</div>
"""

ADMIN_DASH = """
<div class="row mb-3">
  <div class="col-8">
    <h3>Admin dashboard</h3>
    <p class="small-note">Review pending uploads and approve or reject. You can also upload approved material directly.</p>
  </div>
  <div class="col-4 text-end">
    <a class="btn btn-outline-secondary" href="{{ url_for('admin_logout') }}">Logout</a>
  </div>
</div>

<div class="row mb-4">
  <div class="col-md-6">
    <h5>Upload approved material</h5>
    <form method="post" enctype="multipart/form-data" action="{{ url_for('admin_upload') }}">
      <div class="mb-2">
        <select name="subject" class="form-select" required>
          <option value="">Choose subject</option>
          {% for s in subjects.keys() %}
            <option value="{{ s }}">{{ s }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="mb-2">
        <select name="grade" class="form-select" required>
          <option value="">Choose grade</option>
          {% for g in admin_grades %}
            <option value="{{ g }}">Grade {{ g }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="mb-2">
        <input name="files" type="file" accept="application/pdf" class="form-control" required multiple />
      </div>
      <button class="btn btn-success" type="submit">Upload & Approve</button>
    </form>
  </div>
  <div class="col-md-6">
    <h5>Pending uploads</h5>
    {% if pending|length == 0 %}
      <div class="alert alert-secondary">No pending uploads.</div>
    {% else %}
      <div class="list-group">
        {% for p in pending %}
          <div class="list-group-item d-flex justify-content-between align-items-start">
            <div>
              <div class="fw-bold">{{ p.original_name }}</div>
              <div class="small-note">Subject: {{ p.subject }} • Grade: {{ p.grade or '—' }} • Uploaded: {{ p.uploaded_at.split('T')[0] }} • By: {{ p.uploader }}</div>
            </div>
            <div>
              <a class="btn btn-sm btn-outline-primary me-1" href="{{ url_for('admin_view_pending', id=p.id) }}" target="_blank">View</a>
              <a class="btn btn-sm btn-success me-1" href="{{ url_for('admin_approve', id=p.id) }}">Approve</a>
              <a class="btn btn-sm btn-danger" href="{{ url_for('admin_reject', id=p.id) }}">Reject</a>
            </div>
          </div>
        {% endfor %}
      </div>
    {% endif %}
  </div>
</div>
"""

# ----------------------
# Routes
# ----------------------
@app.route('/')
def index():
    return render_template_string(BASE + INDEX, subjects=SUBJECTS)

@app.route('/browse')
def browse():
    subject = request.args.get('subject')
    grade = request.args.get('grade')
    conn = get_db_conn()
    c = conn.cursor()
    query = 'SELECT * FROM uploads WHERE status = ?'
    params = ['approved']
    if subject:
        query += ' AND subject = ?'
        params.append(subject)
    if grade:
        query += ' AND grade = ?'
        params.append(grade)
    query += ' ORDER BY uploaded_at DESC'
    c.execute(query, params)
    rows = c.fetchall()
    files = [dict(r) for r in rows]
    conn.close()

    if subject and subject in SUBJECTS:
        grades_available = SUBJECTS[subject]
    else:
        allg = set()
        for gl in SUBJECTS.values():
            allg.update(gl)
        grades_available = sorted(allg, key=lambda x:int(x))

    return render_template_string(BASE + BROWSE, files=files, subject=subject, grade=grade, grades_available=grades_available)

# ---- Updated user upload (supports multiple files) ----
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        # files field is now 'files' and may contain many FileStorage objects
        if 'files' not in request.files:
            flash('No file part')
            return redirect(request.url)
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(f.filename == '' for f in uploaded_files):
            flash('No selected file(s)')
            return redirect(request.url)

        subject = request.form.get('subject')
        grade = request.form.get('grade')
        uploader = request.form.get('uploader', '').strip()

        if not subject or subject not in SUBJECTS:
            flash('Please choose a valid subject')
            return redirect(request.url)
        if not grade or grade not in SUBJECTS.get(subject, []):
            flash('Please choose a valid grade for the selected subject')
            return redirect(request.url)

        accepted = 0
        rejected = 0
        conn = get_db_conn()
        c = conn.cursor()
        now = datetime.utcnow().isoformat()

        for file in uploaded_files:
            if file and file.filename and allowed_file(file.filename):
                filename, original = save_upload(file, PENDING_DIR)
                c.execute('INSERT INTO uploads (filename, original_name, subject, grade, uploader, status, uploaded_at) VALUES (?,?,?,?,?,?,?)',
                          (filename, original, subject, grade, uploader, 'pending', now))
                accepted += 1
            else:
                rejected += 1
        conn.commit()
        conn.close()

        if accepted:
            flash(f'Uploaded {accepted} file(s). They will be verified by admin.')
        if rejected:
            flash(f'{rejected} file(s) were not accepted (only PDFs allowed).')
        return redirect(url_for('upload'))

    import json
    return render_template_string(BASE + UPLOAD, subjects=SUBJECTS, subjects_json=json.dumps(SUBJECTS))

@app.route('/files/pending/<path:filename>')
def view_pending_file(filename):
    return send_from_directory(PENDING_DIR, filename)

@app.route('/files/approved/<path:filename>')
def view_approved_file(filename):
    return send_from_directory(APPROVED_DIR, filename)

@app.route('/view/<filename>')
def view_file(filename):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM uploads WHERE filename = ? AND status = ?', (filename, 'approved'))
    row = c.fetchone()
    conn.close()
    if not row:
        flash('File not found or not approved')
        return redirect(url_for('browse'))
    return redirect(url_for('view_approved_file', filename=filename))

@app.route('/download/<filename>')
def download_file(filename):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM uploads WHERE filename = ? AND status = ?', (filename, 'approved'))
    row = c.fetchone()
    conn.close()
    if not row:
        flash('File not found or not approved')
        return redirect(url_for('browse'))
    return send_from_directory(APPROVED_DIR, filename, as_attachment=True, download_name=row['original_name'])

# ----------------------
# Admin
# ----------------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if pw == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Wrong password')
            return redirect(url_for('admin_login'))
    return render_template_string(BASE + ADMIN_LOGIN)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Logged out')
    return redirect(url_for('index'))

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            flash('Admin login required')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM uploads WHERE status = ? ORDER BY uploaded_at DESC', ('pending',))
    pending = [dict(r) for r in c.fetchall()]
    conn.close()
    admin_grades = ['8','9','10','11','12']
    return render_template_string(BASE + ADMIN_DASH, pending=pending, subjects=SUBJECTS, admin_grades=admin_grades)

# ---- Updated admin upload (supports multiple files, auto-approved) ----
@app.route('/admin/upload', methods=['POST'])
@admin_required
def admin_upload():
    if 'files' not in request.files:
        flash('No file part')
        return redirect(url_for('admin_dashboard'))

    uploaded_files = request.files.getlist('files')
    if not uploaded_files or all(f.filename == '' for f in uploaded_files):
        flash('No selected file(s)')
        return redirect(url_for('admin_dashboard'))

    subject = request.form.get('subject')
    grade = request.form.get('grade')

    if not subject or subject not in SUBJECTS or not grade:
        flash('Invalid subject/grade')
        return redirect(url_for('admin_dashboard'))

    accepted = 0
    rejected = 0
    conn = get_db_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    for file in uploaded_files:
        if file and file.filename and allowed_file(file.filename):
            filename, original = save_upload(file, APPROVED_DIR)
            c.execute('INSERT INTO uploads (filename, original_name, subject, grade, uploader, status, uploaded_at) VALUES (?,?,?,?,?,?,?)',
                      (filename, original, subject, grade, 'admin', 'approved', now))
            accepted += 1
        else:
            rejected += 1

    conn.commit()
    conn.close()

    if accepted:
        flash(f'Uploaded & approved {accepted} file(s).')
    if rejected:
        flash(f'{rejected} file(s) were not accepted (only PDFs allowed).')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/pending/<int:id>')
@admin_required
def admin_view_pending(id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM uploads WHERE id = ?', (id,))
    row = c.fetchone()
    conn.close()
    if not row:
        flash('Not found')
        return redirect(url_for('admin_dashboard'))
    if row['status'] != 'pending':
        flash('This item is not pending')
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('view_pending_file', filename=row['filename']))

@app.route('/admin/approve/<int:id>')
@admin_required
def admin_approve(id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM uploads WHERE id = ?', (id,))
    row = c.fetchone()
    if not row:
        conn.close()
        flash('Not found')
        return redirect(url_for('admin_dashboard'))
    if row['status'] != 'pending':
        conn.close()
        flash('This item is not pending')
        return redirect(url_for('admin_dashboard'))
    src = os.path.join(PENDING_DIR, row['filename'])
    dst = os.path.join(APPROVED_DIR, row['filename'])
    if os.path.exists(src):
        os.replace(src, dst)
    c.execute('UPDATE uploads SET status = ? WHERE id = ?', ('approved', id))
    conn.commit()
    conn.close()
    flash('Approved')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject/<int:id>')
@admin_required
def admin_reject(id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM uploads WHERE id = ?', (id,))
    row = c.fetchone()
    if not row:
        conn.close()
        flash('Not found')
        return redirect(url_for('admin_dashboard'))
    src = os.path.join(PENDING_DIR, row['filename'])
    if os.path.exists(src):
        os.remove(src)
    c.execute('UPDATE uploads SET status = ? WHERE id = ?', ('rejected', id))
    conn.commit()
    conn.close()
    flash('Rejected and removed')
    return redirect(url_for('admin_dashboard'))

# ----------------------
# Start
# ----------------------
if __name__ == '__main__':
    app.run(debug=True)
