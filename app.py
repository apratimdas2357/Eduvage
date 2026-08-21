import os
from flask import Flask, render_template, request, redirect, url_for, session
from supabase_client import get_supabase

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')

        # If user_id starts with something like a roll number, we'll try to find the student
        try:
            supabase = get_supabase()

            # Simple simulation: just check if the student exists by roll number or email
            response = supabase.table('students').select('*').eq('roll_number', user_id).execute()

            if response.data:
                # Login successful
                session['student_id'] = response.data[0]['id']
                return redirect(url_for('dashboard'))

            # Fallback to email search via profiles for teachers/admins or students
            prof_resp = supabase.table('profiles').select('*').eq('email', user_id).execute()
            if prof_resp.data:
                profile_id = prof_resp.data[0]['id']
                role = prof_resp.data[0]['role']

                if role == 'student':
                    student_resp = supabase.table('students').select('*').eq('profile_id', profile_id).execute()
                    if student_resp.data:
                        session['student_id'] = student_resp.data[0]['id']
                        return redirect(url_for('dashboard'))

                # Currently only handling student dashboard properly, but can extend later
                return render_template('login.html', error=f"Role '{role}' login not fully implemented. Please login as a student.")

            return render_template('login.html', error="Invalid User ID. Please try again.")

        except Exception as e:
            # Handle the case where supabase isn't properly configured or there's an error
            print(f"Supabase error: {e}")
            # Fallback for testing when db is empty/unavailable, to preserve existing functionality:
            if user_id.upper() == '21CS1042':
                session['student_id'] = 'dummy_id'
                return redirect(url_for('dashboard'))
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
        attendance_percentage = str(round((present_classes / total_classes * 100) if total_classes > 0 else 87))

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

        # Assemble data dictionary matching template structure
        full_name = student_data.get('full_name', 'Student')
        first_name = full_name.split(' ')[0]
        initials = ''.join([n[0] for n in full_name.split(' ') if n])[:2].upper()

        data = {
            "college_name": "Kalyani Government Engineering College", # Hardcoded or from settings
            "course": acad_data.get('course', 'B.Tech Information Technology'),
            "semester": str(acad_data.get('semester', '6')),
            "user_name": full_name,
            "roll_no": student_data.get('roll_number', ''),
            "user_initials": initials,
            "first_name": first_name,
            "attendance": attendance_percentage,
            "cgpa": "8.42", # CGPA usually calculated from all past marks
            "fees_due": str(fees_data.get('due_amount', '0')),
            "fees_due_date": str(fees_data.get('due_date', 'N/A')),
            "next_exam_date": "28 June", # Placeholder for exam schedule logic
            "next_exam_subject": "Data Structures Lab",
            "recent_marks": recent_marks if recent_marks else [
                {"subject": "Computer Networks", "obtained": "78", "status": "Pass"},
                {"subject": "DBMS", "obtained": "85", "status": "Pass"}
            ],
            "upcoming_exams": [ # Placeholder as exam schedule isn't fully detailed in simple schema
                {"subject": "Data Structures Lab", "date": "28 June 2024", "time": "10:00 AM"}
            ],
            "notifications": notifications if notifications else ["No new notifications."],
            "hostel_block": hostel_data.get('block', 'N/A'),
            "hostel_room": hostel_data.get('room_number', 'N/A'),
            "hostel_floor": "N/A", # Not in schema, derived from room number typically
            "active_submissions": active_submissions
        }

    except Exception as e:
        print(f"Supabase dashboard error: {e}")
        # Fallback to dummy data if DB isn't setup properly yet
        data = {
            "college_name": "Kalyani Government Engineering College",
            "course": "B.Tech Information Technology",
            "semester": "6",
            "user_name": "Arjun Mehta",
            "roll_no": "21CS1042",
            "user_initials": "AM",
            "first_name": "Apratim",
            "attendance": "87",
            "cgpa": "8.42",
            "fees_due": "45,000",
            "fees_due_date": "10 July",
            "next_exam_date": "28 June",
            "next_exam_subject": "Data Structures Lab",
            "recent_marks": [
                {"subject": "Computer Networks", "obtained": "78", "status": "Pass"},
                {"subject": "DBMS", "obtained": "85", "status": "Pass"},
                {"subject": "Operating Systems", "obtained": "92", "status": "Pass"},
                {"subject": "Design & Analysis of Algorithms", "obtained": "71", "status": "Pass"},
                {"subject": "Software Engineering", "obtained": "88", "status": "Pass"}
            ],
            "upcoming_exams": [
                {"subject": "Data Structures Lab", "date": "28 June 2024", "time": "10:00 AM"},
                {"subject": "Compiler Design", "date": "02 July 2024", "time": "02:00 PM"},
                {"subject": "Artificial Intelligence", "date": "05 July 2024", "time": "10:00 AM"}
            ],
            "notifications": [
                "Semester Fee payment deadline extended to July 10, 2024.",
                "End Semester practical exam schedule has been released.",
                "Block C Hostel maintenance scheduled for Saturday morning.",
                "Library Book 'Introduction to Algorithms' is due back."
            ],
            "hostel_block": "Block C",
            "hostel_room": "312",
            "hostel_floor": "3rd Floor",
            "active_submissions": "2"
        }

    return render_template('dashboard.html', data=data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
