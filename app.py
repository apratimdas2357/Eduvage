import os
from flask import Flask, render_template, request, redirect, url_for, session
from supabase_client import get_supabase

import hashlib

app = Flask(__name__)
# Try to get secret key from env to persist sessions across workers/restarts, otherwise fallback to random
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

def verify_password(stored_password, provided_password):
    # For a real application, you must use something like werkzeug.security.check_password_hash
    # But because our schema defines password_hash and we don't know the exact hashing mechanism used externally,
    # we will just do a direct comparison if it's plain text, or try a simple sha256.
    # The ideal scenario is that the registration system puts properly hashed passwords using bcrypt/werkzeug.
    if stored_password == provided_password:
        return True

    # Try basic SHA-256 hash in case the database actually stores sha256 hashes of the password
    # (Just a fallback to make it slightly more robust for a prototype)
    hashed_provided = hashlib.sha256(provided_password.encode('utf-8')).hexdigest()
    if stored_password == hashed_provided:
        return True

    return False

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
                if role == 'student':
                    student_resp = supabase.table('students').select('*').eq('profile_id', profile['id']).execute()
                    if student_resp.data:
                        session['student_id'] = student_resp.data[0]['id']
                        return redirect(url_for('dashboard'))

                return render_template('login.html', error=f"Role '{role}' login not fully implemented. Please login as a student.")

            return render_template('login.html', error="Invalid User ID.")

        except Exception as e:
            print(f"Supabase error: {e}")
            return render_template('login.html', error="Database error. Please try again later.")

    return render_template('login.html')

@app.route('/dashboard')
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
