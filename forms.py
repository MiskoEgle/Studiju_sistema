from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, FileField, SubmitField, TextAreaField, IntegerField, FloatField, DateTimeField, TimeField, SelectMultipleField, BooleanField, DateField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange, Optional
from wtforms.widgets import ListWidget, CheckboxInput
import re
from flask_wtf.file import FileAllowed
from config import Config

class LoginForm(FlaskForm):
    email = StringField('El. paštas', validators=[DataRequired(), Email()])
    password = PasswordField('Slaptažodis', validators=[DataRequired()])
    remember_me = BooleanField('Prisiminti mane')
    submit = SubmitField('Prisijungti')

class RegistrationForm(FlaskForm):
    email = StringField('El. paštas', validators=[DataRequired(), Email()])
    first_name = StringField('Vardas', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Pavardė', validators=[DataRequired(), Length(min=2, max=50)])
    password = PasswordField('Slaptažodis', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Patvirtinti slaptažodį', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Rolė', choices=[
        ('student', 'Studentas'),
        ('teacher', 'Dėstytojas')
    ], validators=[DataRequired()])
    study_program = SelectField('Studijų programa', coerce=int, validators=[Optional()])
    profile_picture = FileField('Profilio nuotrauka', validators=[Optional(), FileAllowed(['jpg', 'png'], 'Tik JPG ir PNG failai!')])
    submit = SubmitField('Registruotis')
    
    def validate_password(self, field):
        if not re.match(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$', field.data):
            raise ValidationError('Slaptažodis turi būti bent 8 simbolių ilgio ir turėti bent vieną raidę ir vieną skaičių')
    
    def validate_study_program(self, field):
        if self.role.data == 'student' and not field.data:
            raise ValidationError('Studentas privalo pasirinkti studijų programą')

class PasswordChangeForm(FlaskForm):
    current_password = PasswordField('Dabartinis slaptažodis', validators=[DataRequired()])
    new_password = PasswordField('Naujas slaptažodis', validators=[
        DataRequired(),
        Length(min=8, message='Slaptažodis turi būti bent 8 simbolių ilgio')
    ])
    confirm_password = PasswordField('Patvirtinti naują slaptažodį', 
                                   validators=[DataRequired(), EqualTo('new_password', message='Slaptažodžiai turi sutapti')])
    submit = SubmitField('Keisti slaptažodį')
    
    def validate_new_password(self, field):
        if not re.match(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$', field.data):
            raise ValidationError('Slaptažodis turi būti bent 8 simbolių ilgio, turėti bent vieną raidę, vieną skaičių ir vieną specialų simbolį')

class UserForm(FlaskForm):
    email = StringField('El. paštas', validators=[DataRequired(), Email()])
    first_name = StringField('Vardas', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Pavardė', validators=[DataRequired(), Length(min=2, max=50)])
    password = PasswordField('Slaptažodis', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Patvirtinti slaptažodį', validators=[Optional(), EqualTo('password')])
    role = SelectField('Rolė', choices=[('student', 'Studentas'), ('teacher', 'Dėstytojas'), ('admin', 'Administratorius')], validators=[DataRequired()])
    study_program = SelectField('Studijų programa', coerce=int, validators=[Optional()])
    group = SelectField('Grupė', coerce=int, validators=[Optional()])
    is_active = BooleanField('Aktyvus')
    is_approved = BooleanField('Patvirtintas')
    must_change_password = BooleanField('Priverstinai keisti slaptažodį')
    submit = SubmitField('Išsaugoti')
    
    def validate_password(self, field):
        if field.data:  # Only validate password if it's provided
            if not re.match(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$', field.data):
                raise ValidationError('Slaptažodis turi būti bent 8 simbolių ilgio ir turėti bent vieną raidę ir vieną skaičių')

class FacultyForm(FlaskForm):
    name = StringField('Pavadinimas', validators=[DataRequired(), Length(min=2, max=100)])
    code = StringField('Kodas', validators=[DataRequired(), Length(min=2, max=20)])
    description = TextAreaField('Aprašymas', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Išsaugoti')

class StudyProgramForm(FlaskForm):
    name = StringField('Pavadinimas', validators=[DataRequired(), Length(min=2, max=100)])
    code = StringField('Kodas', validators=[DataRequired(), Length(min=2, max=10)])
    faculty_id = SelectField('Fakultetas', coerce=int, validators=[Optional()])
    description = TextAreaField('Aprašymas', validators=[Optional()])
    duration = IntegerField('Trukmė (metais)', validators=[DataRequired(), NumberRange(min=1, max=6)])
    degree = SelectField('Laipsnis', choices=[
        ('bachelor', 'Bakalauras'),
        ('master', 'Magistras'),
        ('phd', 'Doktorantūra')
    ], validators=[DataRequired()])
    submit = SubmitField('Išsaugoti')

class GroupForm(FlaskForm):
    name = StringField('Pavadinimas', validators=[DataRequired(), Length(min=2, max=20)])
    year = IntegerField('Metai', validators=[DataRequired(), NumberRange(min=2000, max=2100)])
    letter = StringField('Raidė', validators=[DataRequired(), Length(min=1, max=1)])
    study_program = SelectField('Studijų programa', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Išsaugoti')

class ModuleForm(FlaskForm):
    name = StringField('Pavadinimas', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Aprašymas', validators=[Optional()])
    credits = IntegerField('Kreditai', validators=[DataRequired(), NumberRange(min=1, max=30)])
    semester = SelectField('Semestras', choices=[('fall', 'Rudens'), ('spring', 'Pavasario')], validators=[DataRequired()])
    study_program = SelectField('Studijų programa', coerce=int, validators=[DataRequired()])
    teacher = SelectField('Dėstytojas', coerce=int, validators=[Optional()])
    prerequisites = SelectMultipleField('Būtinos sąlygos', coerce=int, validators=[Optional()])
    submit = SubmitField('Išsaugoti')

class ScheduleForm(FlaskForm):
    title = StringField('Pavadinimas', validators=[DataRequired()])
    date = DateField('Data', validators=[DataRequired()])
    start_time = TimeField('Pradžios laikas', validators=[DataRequired()])
    end_time = TimeField('Pabaigos laikas', validators=[DataRequired()])
    room = StringField('Auditorija', validators=[DataRequired()])
    type = SelectField('Tipas', choices=[
        ('lecture', 'Paskaita'),
        ('practice', 'Praktinis'),
        ('lab', 'Laboratorinis'),
        ('consultation', 'Konsultacija')
    ], validators=[DataRequired()])

class AssessmentForm(FlaskForm):
    name = StringField('Pavadinimas', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Aprašymas', validators=[Optional()])
    due_date = DateTimeField('Atlikimo data', validators=[DataRequired()])
    weight = FloatField('Svoris (%)', validators=[DataRequired(), NumberRange(min=0, max=100)])
    submit = SubmitField('Išsaugoti')

class GradeForm(FlaskForm):
    grade = FloatField('Pažymys', validators=[DataRequired(), NumberRange(min=1, max=10)])
    feedback = TextAreaField('Atsiliepimas', validators=[Optional()])
    submit = SubmitField('Išsaugoti')

class ModuleEnrollmentForm(FlaskForm):
    module = SelectField('Modulis', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Registruotis į modulį') 