"""
Streamlit Student Enrollment UI

Assumptions:
- The student is already authenticated and logged in. We use the seeded Maya Patel user profile.
- We do not handle login, registration, password management, or new authentication systems.
"""

import streamlit as st
from ai_refactor import EnrollmentDB, EnrollmentManager, DB_PATH, CURRENT_STUDENT

# Initialize backend services
@st.cache_resource
def get_manager():
    db = EnrollmentDB(DB_PATH)
    return EnrollmentManager(db)

manager = get_manager()
user_id = CURRENT_STUDENT["user_id"]
email = CURRENT_STUDENT["email"]

# Initialize state management
if "current_page" not in st.session_state:
    st.session_state.current_page = "dashboard"
if "selected_course" not in st.session_state:
    st.session_state.selected_course = None
if "flash_message" not in st.session_state:
    st.session_state.flash_message = None
if "message_type" not in st.session_state:
    st.session_state.message_type = None

def set_message(msg: str, msg_type: str = "success"):
    st.session_state.flash_message = msg
    st.session_state.message_type = msg_type

def display_message():
    if st.session_state.flash_message:
        if st.session_state.message_type == "success":
            st.success(st.session_state.flash_message)
        else:
            st.error(st.session_state.flash_message)
        st.session_state.flash_message = None
        st.session_state.message_type = None

def change_page(page: str, course=None):
    st.session_state.current_page = page
    st.session_state.selected_course = course

def enroll(key: str):
    result = manager.enroll_with_key(user_id, email, key)
    if result:
        active_classes = manager.get_active_classes(user_id)
        full_course = next(c for c in active_classes if c['course_id'] == result['course_id'])
        
        set_message(f"Successfully enrolled in {result['course_id']}.")
        change_page("class_detail", full_course)
    else:
        set_message("Invalid enrollment key.", "error")

def unenroll(course_id: str):
    success = manager.soft_unenroll_student(user_id, course_id)
    if success:
        set_message(f"Successfully unenrolled from {course_id}.")
    else:
        set_message("Failed to process unenrollment.", "error")

# Page 1: Dashboard
if st.session_state.current_page == "dashboard":
    st.title(f"Dashboard: {CURRENT_STUDENT['name']} ({CURRENT_STUDENT['email']})")
    display_message()

    st.header("Enrolled Classes")
    classes = manager.get_active_classes(user_id)
    
    if not classes:
        st.info("You are not currently enrolled in any classes.")
    else:
        for course in classes:
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(f"{course['course_id']}: {course['course_name']}")
                    st.caption(f"Instructor: {course['instructor']}")
                with col2:
                    if st.button("Go to Class", key=f"go_{course['course_id']}"):
                        change_page("class_detail", course)
                        st.rerun()
                    if st.button("Unenroll", key=f"unenroll_{course['course_id']}"):
                        unenroll(course['course_id'])
                        st.rerun()

    st.divider()
    st.header("Add a Class")
    enrollment_key = st.text_input(
        "Enter Course Enrollment Key", 
        placeholder="E.g. 'MISY350-SPRING'"
    )
    if st.button("Submit Key"):
        if enrollment_key:
            enroll(enrollment_key)
            st.rerun()

# Page 2: Selected Class Detail
elif st.session_state.current_page == "class_detail":
    course = st.session_state.selected_course
    display_message()
    
    if st.button("Return to Dashboard"):
        change_page("dashboard")
        st.rerun()
        
    st.title(course['course_name'])
    st.subheader(course['course_id'])
    st.write(f"**Instructor:** {course['instructor']}")
    st.write(f"**Enrollment Date:** {course['enrolled_at']}")
    
    st.divider()
    st.write("Course modules and materials will appear here.")