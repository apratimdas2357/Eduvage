import os
import uuid
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Cannot seed without SUPABASE_URL and SUPABASE_KEY")
    exit(1)

supabase: Client = create_client(url, key)

def seed():
    try:
        # Seed Profile
        profile_data = {
            "email": "apratim@example.com",
            "role": "student"
        }
        # Insert profile
        p_resp = supabase.table('profiles').insert(profile_data).execute()
        profile_id = p_resp.data[0]['id']

        # Seed Student
        student_data = {
            "profile_id": profile_id,
            "roll_number": "21CS1042",
            "full_name": "Apratim Mehta",
            "phone": "1234567890",
            "address": "Kalyani",
            "emergency_contact": "0987654321"
        }
        s_resp = supabase.table('students').insert(student_data).execute()
        student_id = s_resp.data[0]['id']

        # Seed Academics
        academics_data = {
            "student_id": student_id,
            "course": "B.Tech Information Technology",
            "department": "IT",
            "semester": 6,
            "section": "A",
            "academic_year": "2023-2024",
            "admission_year": 2021
        }
        supabase.table('student_academics').insert(academics_data).execute()

        # Seed Courses & Subjects
        course_resp = supabase.table('courses').insert({"course_name": "B.Tech IT", "department": "IT"}).execute()
        course_id = course_resp.data[0]['id']

        subjects = ["Computer Networks", "DBMS", "Operating Systems", "Design & Analysis of Algorithms", "Software Engineering"]
        sub_ids = []
        for sub in subjects:
            sub_resp = supabase.table('subjects').insert({"course_id": course_id, "subject_name": sub, "semester": 6}).execute()
            sub_ids.append(sub_resp.data[0]['id'])

        # Seed Marks & Exams
        exam_resp = supabase.table('exams').insert({"exam_name": "Mid Semester 6", "semester": 6, "academic_year": "2023-2024"}).execute()
        exam_id = exam_resp.data[0]['id']

        marks_to_insert = [
            {"student_id": student_id, "subject_id": sub_ids[0], "exam_id": exam_id, "marks_obtained": 78, "max_marks": 100},
            {"student_id": student_id, "subject_id": sub_ids[1], "exam_id": exam_id, "marks_obtained": 85, "max_marks": 100},
            {"student_id": student_id, "subject_id": sub_ids[2], "exam_id": exam_id, "marks_obtained": 92, "max_marks": 100},
            {"student_id": student_id, "subject_id": sub_ids[3], "exam_id": exam_id, "marks_obtained": 71, "max_marks": 100},
            {"student_id": student_id, "subject_id": sub_ids[4], "exam_id": exam_id, "marks_obtained": 88, "max_marks": 100}
        ]
        supabase.table('marks').insert(marks_to_insert).execute()

        # Seed Attendance
        attendance = [
            {"student_id": student_id, "subject_id": sub_ids[0], "date": "2024-06-01", "status": "present"},
            {"student_id": student_id, "subject_id": sub_ids[1], "date": "2024-06-01", "status": "present"},
            {"student_id": student_id, "subject_id": sub_ids[2], "date": "2024-06-01", "status": "absent"},
            {"student_id": student_id, "subject_id": sub_ids[3], "date": "2024-06-02", "status": "present"},
            {"student_id": student_id, "subject_id": sub_ids[4], "date": "2024-06-02", "status": "present"}
        ]
        # Adding more present to make it around 87% (e.g. 13 present, 2 absent out of 15)
        for i in range(10):
             attendance.append({"student_id": student_id, "subject_id": sub_ids[0], "date": f"2024-06-{i+5:02d}", "status": "present"})
        supabase.table('attendance').insert(attendance).execute()

        # Seed Fees
        fees_data = {
            "student_id": student_id,
            "total_amount": 90000,
            "paid_amount": 45000,
            "due_amount": 45000,
            "due_date": "2024-07-10"
        }
        supabase.table('fees').insert(fees_data).execute()

        # Seed Applications
        apps = [
            {"student_id": student_id, "application_type": "Hostel Leave", "status": "pending"},
            {"student_id": student_id, "application_type": "Library Card Renewal", "status": "pending"}
        ]
        supabase.table('applications').insert(apps).execute()

        # Seed Hostel
        hostel_data = {
            "student_id": student_id,
            "hostel_name": "Main Boys Hostel",
            "block": "Block C",
            "room_number": "312",
            "academic_year": "2023-2024"
        }
        supabase.table('hostel').insert(hostel_data).execute()

        # Seed Notifications
        notifications = [
            {"student_id": student_id, "title": "Fee Deadline", "message": "Semester Fee payment deadline extended to July 10, 2024.", "category": "Fees"},
            {"student_id": student_id, "title": "Exam Schedule", "message": "End Semester practical exam schedule has been released.", "category": "Exams"},
            {"student_id": student_id, "title": "Hostel Maintenance", "message": "Block C Hostel maintenance scheduled for Saturday morning.", "category": "Hostel"},
            {"student_id": student_id, "title": "Library Due", "message": "Library Book 'Introduction to Algorithms' is due back.", "category": "Library"}
        ]
        supabase.table('notifications').insert(notifications).execute()

        print("Database seeded successfully!")

    except Exception as e:
        print(f"Error seeding database: {e}")

if __name__ == '__main__':
    seed()
