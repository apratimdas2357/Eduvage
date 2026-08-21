from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    # Dummy data based on the provided dashboard image
    data = {
        "college_name": "Kalyani Government Engineering College",
        "course": "B.Tech Information Technology",
        "semester": "6",
        "user_name": "Arjun Mehta",
        "roll_no": "21CS1042",
        "user_initials": "AM",
        "first_name": "Apratim",  # The image says "Welcome back, Apratim" but top right is Arjun Mehta. I'll stick to the text in the image.
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
