import os
from functools import wraps
import threading
import time
import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from supabase_client import get_supabase

from werkzeug.security import generate_password_hash, check_password_hash
import hashlib

app = Flask(__name__)
# Try to get secret key from env to persist sessions across workers/restarts, otherwise fallback to random
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

def keep_alive():
    """Background thread to ping the server and prevent sleeping on Render."""
    url = os.environ.get('RENDER_EXTERNAL_URL', 'http://127.0.0.1:5000')
    if not url.endswith('/ping'):
        url = url + '/ping'
    while True:
        try:
            requests.get(url, timeout=10)
        except Exception:
            pass
        time.sleep(600) # Ping every 10 minutes

# Start keep-alive thread
threading.Thread(target=keep_alive, daemon=True).start()

@app.route('/ping')
def ping():
    return jsonify(status="ok"), 200

def requires_role(role_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('role')
            if not user_role or user_role != role_name:
                return redirect(url_for('login', error="Unauthorized access. Please login with correct role."))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def verify_password(stored_password, provided_password):
    if stored_password == provided_password:
        return True
    # If the hash starts with pbkdf2:sha256 or scrypt (werkzeug default)
    try:
        if check_password_hash(stored_password, provided_password):
            return True
    except:
        pass

    # Fallback to sha256 for backward compatibility with existing tests/data
    hashed_provided = hashlib.sha256(provided_password.encode('utf-8')).hexdigest()
    if stored_password == hashed_provided:
        return True

    return False

@app.route('/apply', methods=['GET', 'POST'])
def apply():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            supabase = get_supabase()

            # Check if email exists
            existing = supabase.table('profiles').select('id').eq('email', email).execute()
            if existing.data:
                return render_template('apply.html', error="Email already exists.")

            # Hash using werkzeug
            hashed_pw = generate_password_hash(password)

            # Insert profile with 'student' role (pending approval logic handles access)
            prof_resp = supabase.table('profiles').insert({
                'email': email,
                'password_hash': hashed_pw,
                'role': 'student'
            }).execute()

            if prof_resp.data:
                profile_id = prof_resp.data[0]['id']
                # Do NOT insert into students yet, wait for admin approval
                # Admin dashboard will query profiles with role 'student' that do NOT have a student record

                return redirect(url_for('login', error="Application submitted successfully. Waiting for admin approval."))

        except Exception as e:
            print(f"Apply error: {e}")
            return render_template('apply.html', error="An error occurred during application.")

    return render_template('apply.html')


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')

        try:
            supabase = get_supabase()

            # 1. Search by email directly in profiles
            prof_resp = supabase.table('profiles').select('*').eq('email', user_id).execute()

            # 2. If not found by email, try searching students by roll_number to get profile_id
            if not prof_resp.data:
                student_search = supabase.table('students').select('profile_id').eq('roll_number', user_id).execute()
                if student_search.data:
                    prof_resp = supabase.table('profiles').select('*').eq('id', student_search.data[0]['profile_id']).execute()

            if prof_resp.data:
                profile = prof_resp.data[0]

                # Check password
                stored_hash = profile.get('password_hash')
                if not stored_hash or not verify_password(stored_hash, password):
                    return render_template('login.html', error="Invalid Password.")

                role = profile.get('role')
                # Role check from form
                expected_role = request.form.get('role')
                if role != expected_role:
                    return render_template('login.html', error=f"User is not a {expected_role}.")

                if role == 'student':
                    student_resp = supabase.table('students').select('*').eq('profile_id', profile['id']).execute()
                    if student_resp.data:
                        session['student_id'] = student_resp.data[0]['id']
                        session['role'] = 'student'
                        return redirect(url_for('dashboard'))
                    else:
                        return render_template('login.html', error="Your application is still pending approval.")
                elif role == 'teacher':
                    teacher_resp = supabase.table('teachers').select('*').eq('profile_id', profile['id']).execute()
                    if teacher_resp.data:
                        session['teacher_id'] = teacher_resp.data[0]['id']
                        session['role'] = 'teacher'
                        return redirect(url_for('teacher_dashboard'))
                elif role == 'admin':
                    session['admin_id'] = profile['id']
                    session['role'] = 'admin'
                    return redirect(url_for('admin_dashboard'))

                return render_template('login.html', error=f"Role '{role}' login failed to retrieve profile.")

            return render_template('login.html', error="Invalid User ID.")

        except Exception as e:
            print(f"Supabase error: {e}")
            return render_template('login.html', error="Database error. Please try again later.")

    error = request.args.get('error')
    return render_template('login.html', error=error)

def get_student_common_data(student_id):
    """Helper function to fetch common data like name, roll_no, etc. for the header."""
    supabase = get_supabase()
    student_resp = supabase.table('students').select('*').eq('id', student_id).execute()
    student_data = student_resp.data[0] if student_resp.data else {}
    full_name = student_data.get('full_name', 'Student')
    initials = ''.join([n[0] for n in full_name.split(' ') if n])[:2].upper()
    return {
        "user_name": full_name,
        "roll_no": student_data.get('roll_number', ''),
        "user_initials": initials,
    }

@app.route('/profile')
@requires_role('student')
def student_profile():
    student_id = session.get('student_id')
    if not student_id: return redirect(url_for('login'))

    try:
        supabase = get_supabase()
        student_resp = supabase.table('students').select('*, profiles(email)').eq('id', student_id).execute()
        student_data = student_resp.data[0] if student_resp.data else {}

        acad_resp = supabase.table('student_academics').select('*').eq('student_id', student_id).execute()
        acad_data = acad_resp.data[0] if acad_resp.data else {}

        full_name = student_data.get('full_name', 'Student')
        initials = ''.join([n[0] for n in full_name.split(' ') if n])[:2].upper()

        data = {
            "user_name": full_name,
            "roll_no": student_data.get('roll_number', ''),
            "user_initials": initials,
            "email": student_data.get('profiles', {}).get('email', 'N/A'),
            "dob": student_data.get('date_of_birth', 'N/A'),
            "phone": student_data.get('phone', 'N/A'),
            "address": student_data.get('address', 'N/A'),
            "emergency_contact": student_data.get('emergency_contact', 'N/A'),

            "course": acad_data.get('course', 'N/A'),
            "department": acad_data.get('department', 'N/A'),
            "semester": str(acad_data.get('semester', 'N/A')),
            "section": acad_data.get('section', 'N/A'),
            "admission_year": str(acad_data.get('admission_year', 'N/A')),
            "college_name": os.environ.get("COLLEGE_NAME", "Kalyani Government Engineering College"),
        }
        return render_template('profile.html', data=data)
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return redirect(url_for('dashboard'))

@app.route('/attendance')
@requires_role('student')
def attendance():
    student_id = session.get('student_id')
    if not student_id: return redirect(url_for('login'))

    try:
        data = get_student_common_data(student_id)
        supabase = get_supabase()
        att_resp = supabase.table('attendance').select('*, subjects(subject_name)').eq('student_id', student_id).execute()
        data['attendance_records'] = att_resp.data
        return render_template('attendance.html', data=data)
    except Exception as e:
        return redirect(url_for('dashboard'))

@app.route('/marks')
@requires_role('student')
def marks():
    student_id = session.get('student_id')
    if not student_id: return redirect(url_for('login'))

    try:
        data = get_student_common_data(student_id)
        supabase = get_supabase()
        marks_resp = supabase.table('marks').select('*, subjects(subject_name), exams(exam_name)').eq('student_id', student_id).execute()
        data['marks_records'] = marks_resp.data
        return render_template('marks.html', data=data)
    except Exception as e:
        return redirect(url_for('dashboard'))

@app.route('/fees')
@requires_role('student')
def fees():
    student_id = session.get('student_id')
    if not student_id: return redirect(url_for('login'))

    try:
        data = get_student_common_data(student_id)
        supabase = get_supabase()
        fees_resp = supabase.table('fees').select('*').eq('student_id', student_id).execute()
        payments_resp = supabase.table('payments').select('*').eq('student_id', student_id).execute()
        data['fee_details'] = fees_resp.data[0] if fees_resp.data else {}
        data['payments'] = payments_resp.data
        return render_template('fees.html', data=data)
    except Exception as e:
        return redirect(url_for('dashboard'))

@app.route('/hostel')
@requires_role('student')
def hostel():
    student_id = session.get('student_id')
    if not student_id: return redirect(url_for('login'))

    try:
        data = get_student_common_data(student_id)
        supabase = get_supabase()
        hostel_resp = supabase.table('hostel').select('*').eq('student_id', student_id).execute()
        data['hostel_details'] = hostel_resp.data[0] if hostel_resp.data else None
        return render_template('hostel.html', data=data)
    except Exception as e:
        return redirect(url_for('dashboard'))

@app.route('/applications')
@requires_role('student')
def applications():
    student_id = session.get('student_id')
    if not student_id: return redirect(url_for('login'))

    try:
        data = get_student_common_data(student_id)
        supabase = get_supabase()
        app_resp = supabase.table('applications').select('*').eq('student_id', student_id).execute()
        data['applications'] = app_resp.data
        return render_template('applications.html', data=data)
    except Exception as e:
        return redirect(url_for('dashboard'))

@app.route('/notifications')
@requires_role('student')
def notifications():
    student_id = session.get('student_id')
    if not student_id: return redirect(url_for('login'))

    try:
        data = get_student_common_data(student_id)
        supabase = get_supabase()
        notif_resp = supabase.table('notifications').select('*').eq('student_id', student_id).order('created_at', desc=True).execute()
        data['notifications'] = notif_resp.data
        return render_template('notifications.html', data=data)
    except Exception as e:
        return redirect(url_for('dashboard'))

@app.route('/settings')
@requires_role('student')
def settings():
    student_id = session.get('student_id')
    if not student_id: return redirect(url_for('login'))
    data = get_student_common_data(student_id)
    return render_template('settings.html', data=data)

@app.route('/dashboard')
@requires_role('student')
def dashboard():
    student_id = session.get('student_id')
    if not student_id:
        return redirect(url_for('login'))

    try:
        supabase = get_supabase()

        # In a real scenario, we'd query all the related tables using the student_id
        # For this prototype to seamlessly integrate but show real db records when available:

        # 1. Get Student details
        student_resp = supabase.table('students').select('*').eq('id', student_id).execute()

        if not student_resp.data:
            raise Exception("Student not found")

        student_data = student_resp.data[0]

        # 2. Get Academic details
        acad_resp = supabase.table('student_academics').select('*').eq('student_id', student_id).execute()
        acad_data = acad_resp.data[0] if acad_resp.data else {}

        # 3. Get Attendance (simplified aggregation for prototype)
        att_resp = supabase.table('attendance').select('status').eq('student_id', student_id).execute()
        total_classes = len(att_resp.data)
        present_classes = sum(1 for a in att_resp.data if a['status'] == 'present')
        attendance_percentage = str(round((present_classes / total_classes * 100) if total_classes > 0 else 0))

        # 4. Get Marks
        marks_resp = supabase.table('marks').select('*, subjects(subject_name)').eq('student_id', student_id).execute()
        recent_marks = []
        for mark in marks_resp.data:
            status = "Pass" if (mark.get('marks_obtained', 0) / mark.get('max_marks', 1)) >= 0.4 else "Fail"
            recent_marks.append({
                "subject": mark.get('subjects', {}).get('subject_name', 'Unknown Subject'),
                "obtained": mark.get('marks_obtained'),
                "status": status
            })

        cgpa = "N/A"
        if len(marks_resp.data) > 0:
            total_marks = sum(mark.get('marks_obtained', 0) for mark in marks_resp.data)
            max_marks = sum(mark.get('max_marks', 100) for mark in marks_resp.data)
            # Rough CGPA estimation for demonstration since it's not directly in DB
            cgpa = str(round((total_marks / max_marks) * 10, 2))

        # 5. Get Fees
        fees_resp = supabase.table('fees').select('*').eq('student_id', student_id).execute()
        fees_data = fees_resp.data[0] if fees_resp.data else {"due_amount": 0, "due_date": "N/A"}

        # 6. Get Hostel
        hostel_resp = supabase.table('hostel').select('*').eq('student_id', student_id).execute()
        hostel_data = hostel_resp.data[0] if hostel_resp.data else {"block": "N/A", "room_number": "N/A"}

        # 7. Get Notifications
        notif_resp = supabase.table('notifications').select('message').eq('student_id', student_id).order('created_at', desc=True).limit(4).execute()
        notifications = [n['message'] for n in notif_resp.data]

        # 8. Applications
        app_resp = supabase.table('applications').select('id').eq('student_id', student_id).eq('status', 'pending').execute()
        active_submissions = str(len(app_resp.data))

        # 9. Upcoming Exams
        exams_resp = supabase.table('exams').select('*').execute()
        # Since 'upcoming exams' specific data structure doesn't fully match schema fields like 'time' and 'date' for subject level exams directly,
        # we will extract from exams table. This schema just has exam_name and academic year.
        upcoming_exams = []
        if exams_resp.data:
            for exam in exams_resp.data[:3]: # Limit to 3
                upcoming_exams.append({"subject": exam.get('exam_name', 'Exam'), "date": exam.get('academic_year', 'TBD'), "time": "TBD"})

        next_exam_date = upcoming_exams[0]['date'] if upcoming_exams else "N/A"
        next_exam_subject = upcoming_exams[0]['subject'] if upcoming_exams else "N/A"

        # Assemble data dictionary matching template structure
        full_name = student_data.get('full_name', 'Student')
        first_name = full_name.split(' ')[0]
        initials = ''.join([n[0] for n in full_name.split(' ') if n])[:2].upper()

        # Use an env variable for college name or fallback
        college_name = os.environ.get("COLLEGE_NAME", "Eduvage University")

        data = {
            "college_name": college_name,
            "course": acad_data.get('course', 'N/A') if acad_data else 'N/A',
            "semester": str(acad_data.get('semester', 'N/A')) if acad_data else 'N/A',
            "user_name": full_name,
            "roll_no": student_data.get('roll_number', ''),
            "user_initials": initials,
            "first_name": first_name,
            "attendance": attendance_percentage,
            "cgpa": cgpa,
            "fees_due": str(fees_data.get('due_amount', '0')),
            "fees_due_date": str(fees_data.get('due_date', 'N/A')),
            "next_exam_date": next_exam_date,
            "next_exam_subject": next_exam_subject,
            "recent_marks": recent_marks,
            "upcoming_exams": upcoming_exams,
            "notifications": notifications if notifications else ["No new notifications."],
            "hostel_block": hostel_data.get('block', 'N/A'),
            "hostel_room": hostel_data.get('room_number', 'N/A'),
            "hostel_floor": "N/A", # Not in schema, derived from room number typically
            "active_submissions": active_submissions
        }

    except Exception as e:
        print(f"Supabase dashboard error: {e}")
        return render_template('login.html', error="Failed to fetch dashboard data. Please log in again.")

    return render_template('dashboard.html', data=data)

@app.route('/teacher_dashboard')
@requires_role('teacher')
def teacher_dashboard():
    teacher_id = session.get('teacher_id')
    if not teacher_id:
        return redirect(url_for('login'))

    try:
        supabase = get_supabase()

        # Get Teacher details
        teacher_resp = supabase.table('teachers').select('*').eq('id', teacher_id).execute()

        if not teacher_resp.data:
            raise Exception("Teacher not found")

        teacher_data = teacher_resp.data[0]

        # Get Subjects taught by teacher via teacher_subjects
        ts_resp = supabase.table('teacher_subjects').select('subject_id, subjects(*)').eq('teacher_id', teacher_id).execute()
        subjects = [ts.get('subjects') for ts in ts_resp.data if ts.get('subjects')]

        # We need a list of students to mark attendance/marks for the subjects taught
        # For simplicity, let's just get all students
        students_resp = supabase.table('students').select('id, full_name, roll_number').execute()
        students = students_resp.data

        full_name = teacher_data.get('full_name', 'Teacher')
        initials = ''.join([n[0] for n in full_name.split(' ') if n])[:2].upper()

        data = {
            "user_name": full_name,
            "user_initials": initials,
            "subjects": subjects,
            "students": students,
        }

    except Exception as e:
        print(f"Supabase teacher dashboard error: {e}")
        return render_template('login.html', error="Failed to fetch dashboard data.")

    return render_template('teacher_dashboard.html', data=data)

@app.route('/admin_dashboard')
@requires_role('admin')
def admin_dashboard():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('login'))

    try:
        supabase = get_supabase()
        # Admin can view all users
        profiles_resp = supabase.table('profiles').select('*').execute()

        # Get all approved students to distinguish from pending
        students_resp = supabase.table('students').select('profile_id').execute()
        approved_student_profile_ids = [s['profile_id'] for s in students_resp.data] if students_resp.data else []

        pending = []
        active = []

        for p in profiles_resp.data:
            if p.get('role') == 'student' and p.get('id') not in approved_student_profile_ids:
                pending.append(p)
            else:
                active.append(p)

        data = {
            "user_name": "Admin User",
            "user_initials": "AD",
            "pending_profiles": pending,
            "active_profiles": active
        }
    except Exception as e:
        print(f"Supabase admin dashboard error: {e}")
        return render_template('login.html', error="Failed to fetch admin data.")

    return render_template('admin_dashboard.html', data=data)

@app.route('/approve_application', methods=['POST'])
@requires_role('admin')
def approve_application():
    profile_id = request.form.get('profile_id')
    roll_number = request.form.get('roll_number')

    try:
        supabase = get_supabase()
        # Update profile role to student
        supabase.table('profiles').update({'role': 'student'}).eq('id', profile_id).execute()

        # Check if student record exists first, if not INSERT
        existing_student = supabase.table('students').select('id').eq('profile_id', profile_id).execute()

        if existing_student.data:
             # Update student roll number
             supabase.table('students').update({'roll_number': roll_number}).eq('profile_id', profile_id).execute()
        else:
             # We need a full_name, but we don't have it saved from the apply form.
             # Let's see if we can extract it from the email or default it
             # Ideally apply form should save pending students in another table, but for now we fallback
             profile_resp = supabase.table('profiles').select('email').eq('id', profile_id).execute()
             email = profile_resp.data[0]['email'] if profile_resp.data else 'Unknown'
             full_name = email.split('@')[0].replace('.', ' ').title()

             supabase.table('students').insert({
                 'profile_id': profile_id,
                 'full_name': full_name,
                 'roll_number': roll_number
             }).execute()

    except Exception as e:
        print(f"Error approving application: {e}")

    return redirect(url_for('admin_dashboard'))

@app.route('/update_marks', methods=['POST'])
@requires_role('teacher')
def update_marks():
    student_id = request.form.get('student_id')
    subject_id = request.form.get('subject_id')
    marks_obtained = request.form.get('marks_obtained')

    try:
        supabase = get_supabase()
        # Upsert or Insert marks. Let's try to update if exists, else insert.
        # But for simplicity in this prototype, just insert a new record or update by filtering
        existing = supabase.table('marks').select('*').eq('student_id', student_id).eq('subject_id', subject_id).execute()
        if existing.data:
            supabase.table('marks').update({'marks_obtained': marks_obtained}).eq('id', existing.data[0]['id']).execute()
        else:
            supabase.table('marks').insert({
                'student_id': student_id,
                'subject_id': subject_id,
                'marks_obtained': marks_obtained,
                'max_marks': 100
            }).execute()
    except Exception as e:
        print(f"Error updating marks: {e}")

    return redirect(url_for('teacher_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
