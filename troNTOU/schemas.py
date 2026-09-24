from pydantic import BaseModel

# i like gemini-chan
__all__ = ["Rollcall", "VisitedCourses", "StudentRollcall", "Config"]

# --- rollcall ---
class _rollcall(BaseModel):
    avatar_big_url: str
    class_name: str
    course_id: int
    course_title: str
    created_by: int
    created_by_name: str
    department_name: str
    grade_name: str
    group_set_id: int
    is_expired: bool
    is_number: bool
    is_radar: bool
    published_at: str | None
    rollcall_id: int
    rollcall_status: str
    rollcall_time: str
    scored: bool
    source: str
    status: str
    student_rollcall_id: int
    title: str
    type: str

class Rollcall(BaseModel):
    rollcalls: list[_rollcall]


# --- recently-visited-courses ---
class CourseAttributes(BaseModel):
    teaching_class_name: str | None
    
class Course_Department(BaseModel):
    name: str
    
class Course_Grade(BaseModel):
    name: str
    
class Course_Klass(BaseModel):
    name: str

class Course(BaseModel):
    course_attributes: CourseAttributes
    course_code: str
    course_type: int
    cover: str
    current_user_is_member: bool
    department: Course_Department
    grade: Course_Grade
    id: int
    klass: Course_Klass
    name: str
    org_id: int
    teaching_unit_type: str
    url: str

class VisitedCourses(BaseModel):
    visited_courses: list[Course]


# --- rollcall-detail ---
class Detail_Department(BaseModel):
    code: str
    id: int
    name: str
    
class Detail_Grade(BaseModel):
    id: int
    name: str

class Detail_Klass(BaseModel):
    code: str | None
    id: int
    name: str

class StudentRollcall(BaseModel):
    comment: str | None
    department: Detail_Department
    distance: float | None
    grade: Detail_Grade
    klass: Detail_Klass
    name: str
    nickname: str | None
    rollcall_status: str
    status: str
    status_detail: str
    student_id: int
    updated_at: str
    user_no: str

class StudentRollcall(BaseModel):
    comment: str | None
    end_time: str
    external_api_key_id: int | None
    is_number: bool
    is_radar: bool
    number_code: str
    published_at: str | None
    scored: bool
    section: str
    status: str
    student_rollcalls: list[StudentRollcall]
    title: str
    type: str

# --- user's config ---
class Account(BaseModel):
    user: str
    passwd: str

class NotificationChannel(BaseModel):
    enable: bool
    key: str
    chat: str

class Notifications(BaseModel):
    tg: NotificationChannel
    dc: NotificationChannel

class GeneralConfig(BaseModel):
    enable_log: bool
    Senkaku: int
    retries: int
class OperatingDay(BaseModel):
    enable: bool
    range: list[str]

class Config(BaseModel):
    account: Account
    notifications: Notifications
    config: GeneralConfig
    operating: dict[int, OperatingDay]