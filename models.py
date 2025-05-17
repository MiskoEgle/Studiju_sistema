from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db

# Association tables
module_student = db.Table('module_student',
    db.Column('module_id', db.Integer, db.ForeignKey('module.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('enrolled_at', db.DateTime, default=datetime.utcnow)
)

module_prerequisite = db.Table('module_prerequisite',
    db.Column('module_id', db.Integer, db.ForeignKey('module.id'), primary_key=True),
    db.Column('prerequisite_id', db.Integer, db.ForeignKey('module.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    profile_picture = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    is_approved = db.Column(db.Boolean, default=False)
    force_password_change = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    phone_number = db.Column(db.String(20))
    last_login = db.Column(db.DateTime)
    
    # Relationships
    study_program_id = db.Column(db.Integer, db.ForeignKey('study_program.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    study_program = db.relationship('StudyProgram', back_populates='students')
    group = db.relationship('Group', back_populates='students')
    enrolled_modules = db.relationship('Module', secondary=module_student, back_populates='students')
    grades = db.relationship('Grade', back_populates='student')
    modules = db.relationship('Module', back_populates='teacher', foreign_keys='Module.teacher_id')
    assessments = db.relationship('Assessment', back_populates='teacher', foreign_keys='Assessment.teacher_id')
    submissions = db.relationship('AssessmentSubmission', back_populates='student')
    
    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_teacher(self):
        return self.role == 'teacher'
    
    @property
    def is_student(self):
        return self.role == 'student'
    
    @classmethod
    def get_by_email(cls, email):
        return db.session.execute(
            db.select(cls).where(cls.email == email)
        ).scalar_one_or_none()
    
    @classmethod
    def get_all(cls):
        result = db.session.execute(
            db.select(cls)
        ).scalars().all()
        return result
    
    @classmethod
    def get_by_role(cls, role):
        return db.session.execute(
            db.select(cls).where(cls.role == role)
        ).scalars().all()

    def save(self):
        try:
            db.session.add(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

    def delete(self):
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

class Faculty(db.Model):
    __tablename__ = 'faculty'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    study_programs = db.relationship('StudyProgram', back_populates='faculty', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Faculty {self.name}>'
    
    def save(self):
        try:
            db.session.add(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False
    
    def delete(self):
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False
            
    @classmethod
    def get_all(cls):
        result = db.session.execute(
            db.select(cls)
        ).scalars().all()
        return result

class StudyProgram(db.Model):
    __tablename__ = 'study_program'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), nullable=False, unique=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.id'), nullable=False)
    description = db.Column(db.Text)
    duration = db.Column(db.Integer, nullable=False)
    degree = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    faculty = db.relationship('Faculty', back_populates='study_programs')
    modules = db.relationship('Module', back_populates='study_program', cascade='all, delete-orphan')
    students = db.relationship('User', back_populates='study_program')
    groups = db.relationship('Group', back_populates='study_program', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<StudyProgram {self.name}>'

    @classmethod
    def get_all(cls):
        result = db.session.execute(
            db.select(cls)
        ).scalars().all()
        return result
    
    @classmethod
    def get_by_faculty(cls, faculty_id):
        result = db.session.execute(
            db.select(cls).where(cls.faculty_id == faculty_id)
        ).scalars().all()
        return result

class Group(db.Model):
    __tablename__ = 'group'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    study_program_id = db.Column(db.Integer, db.ForeignKey('study_program.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    study_program = db.relationship('StudyProgram', back_populates='groups')
    students = db.relationship('User', back_populates='group')

    def __repr__(self):
        return f'<Group {self.name}>'

    @classmethod
    def get_all(cls):
        result = db.session.execute(
            db.select(cls)
        ).scalars().all()
        return result
    
    @classmethod
    def get_by_study_program(cls, study_program_id):
        result = db.session.execute(
            db.select(cls).where(cls.study_program_id == study_program_id)
        ).scalars().all()
        return result

class Module(db.Model):
    __tablename__ = 'module'
    
    id = db.Column(db.Integer, primary_key=True)
    study_program_id = db.Column(db.Integer, db.ForeignKey('study_program.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    credits = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    study_program = db.relationship('StudyProgram', back_populates='modules')
    teacher = db.relationship('User', back_populates='modules')
    assessments = db.relationship('Assessment', back_populates='module', cascade='all, delete-orphan')
    students = db.relationship('User', secondary=module_student, back_populates='enrolled_modules')
    prerequisites = db.relationship(
        'Module',
        secondary=module_prerequisite,
        primaryjoin=(id == module_prerequisite.c.module_id),
        secondaryjoin=(id == module_prerequisite.c.prerequisite_id),
        backref=db.backref('dependent_modules', lazy='dynamic')
    )

    def __repr__(self):
        return f'<Module {self.name}>'

    @classmethod
    def get_all(cls):
        return db.session.execute(db.select(cls)).scalars().all()

    @classmethod
    def get_by_id(cls, id):
        return db.session.get(cls, id)

    @classmethod
    def get_by_study_program(cls, study_program_id):
        return db.session.execute(
            db.select(cls).where(cls.study_program_id == study_program_id)
        ).scalars().all()

    @classmethod
    def get_by_teacher(cls, teacher_id):
        return db.session.execute(
            db.select(cls).where(cls.teacher_id == teacher_id)
        ).scalars().all()

    def save(self):
        try:
            db.session.add(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

    def delete(self):
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

class Schedule(db.Model):
    __tablename__ = 'schedule'
    
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('module.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    room = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    
    # Relationships
    module = db.relationship('Module', backref='schedule_entries')
    group = db.relationship('Group', backref='schedule_entries')
    attendance_records = db.relationship('Attendance', backref='schedule', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Schedule {self.module.name} {self.date} {self.start_time}-{self.end_time}>'

    @classmethod
    def get_by_module(cls, module_id):
        return db.session.execute(
            db.select(cls)
            .filter_by(module_id=module_id)
            .order_by(cls.date, cls.start_time)
        ).scalars().all()

    @classmethod
    def get_by_group(cls, group_id):
        return db.session.execute(
            db.select(cls)
            .filter_by(group_id=group_id)
            .order_by(cls.date, cls.start_time)
        ).scalars().all()

    def save(self):
        try:
            db.session.add(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

    def delete(self):
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student = db.relationship('User', backref='attendance_records')

    def __repr__(self):
        return f'<Attendance {self.student.full_name} - {self.schedule.title} - {self.status}>'

class Assessment(db.Model):
    __tablename__ = 'assessment'
    
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('module.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    weight_percentage = db.Column(db.Integer, nullable=False)
    grading_scale = db.Column(db.String(20), nullable=False, default='10_POINT')  # 10_POINT, 100_POINT, PERCENTAGE
    max_points = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    module = db.relationship('Module', back_populates='assessments')
    teacher = db.relationship('User', back_populates='assessments')
    grades = db.relationship('Grade', back_populates='assessment', cascade='all, delete-orphan')
    submissions = db.relationship('AssessmentSubmission', back_populates='assessment', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Assessment {self.title}>'

    @property
    def is_ten_point(self):
        return self.grading_scale == '10_POINT'

    @property
    def is_hundred_point(self):
        return self.grading_scale == '100_POINT'

    @property
    def is_percentage(self):
        return self.grading_scale == 'PERCENTAGE'

    def convert_grade(self, points):
        """Convert raw points to the selected grading scale"""
        if points is None:
            return None
            
        percentage = (points / self.max_points) * 100
        
        if self.is_ten_point:
            if percentage >= 95: return 10
            elif percentage >= 85: return 9
            elif percentage >= 75: return 8
            elif percentage >= 65: return 7
            elif percentage >= 55: return 6
            elif percentage >= 45: return 5
            else: return 4
        elif self.is_hundred_point:
            return round(percentage)
        else:  # percentage
            return round(percentage, 1)

    def save(self):
        try:
            db.session.add(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

    def delete(self):
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

class Grade(db.Model):
    __tablename__ = 'grade'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)
    grade = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship('User', back_populates='grades')
    assessment = db.relationship('Assessment', back_populates='grades')

    def __repr__(self):
        return f'<Grade {self.grade}>'

    @classmethod
    def get_by_assessment(cls, assessment_id):
        return db.session.execute(
            db.select(cls).where(cls.assessment_id == assessment_id)
        ).scalars().all()

    @classmethod
    def get_by_student(cls, student_id):
        return db.session.execute(
            db.select(cls).where(cls.student_id == student_id)
        ).scalars().all()

    @classmethod
    def get_by_assessment_and_student(cls, assessment_id, student_id):
        return db.session.execute(
            db.select(cls).where(
                cls.assessment_id == assessment_id,
                cls.student_id == student_id
            )
        ).scalar_one_or_none()

    def save(self):
        try:
            db.session.add(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

    def delete(self):
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False 

class AssessmentSubmission(db.Model):
    __tablename__ = 'assessment_submission'
    
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    submission_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    grade = db.Column(db.Float)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    assessment = db.relationship('Assessment', back_populates='submissions')
    student = db.relationship('User', back_populates='submissions')

    def __repr__(self):
        return f'<AssessmentSubmission {self.id}>' 