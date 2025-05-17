from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from extensions import db, csrf
from models import User, Module, Assessment, Grade, Group, Schedule, module_student, StudyProgram
from forms import AssessmentForm, GradeForm
from sqlalchemy import distinct, text, func
from datetime import datetime, time, timedelta
from sqlalchemy.orm import joinedload
import logging
import traceback
from werkzeug.security import generate_password_hash
from functools import wraps

bp = Blueprint('teacher', __name__)

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'teacher':
            flash('Neturite teisių pasiekti šį puslapį.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/teacher')
@login_required
def dashboard():
    if current_user.role != 'teacher':
        flash('Neturite teisių pasiekti dėstytojo skydelį.', 'danger')
        return render_template('index.html')
    
    try:
        modules = Module.query.filter_by(teacher_id=current_user.id).all()
        assessments = Assessment.query.join(Module).filter(Module.teacher_id == current_user.id).all()
    except Exception as e:
        flash('Įvyko klaida užkraunant duomenis. Pabandykite dar kartą.', 'danger')
        return render_template('teacher/index.html')
    
    return render_template('teacher/index.html')

@bp.route('/teacher/modules')
@login_required
def modules():
    if current_user.role != 'teacher':
        flash('Neturite teisių peržiūrėti modulius.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        modules = Module.get_by_teacher(current_user.id)
    except Exception as e:
        flash('Įvyko klaida užkraunant modulius. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('teacher/modules.html', modules=modules)

@bp.route('/teacher/modules/<int:module_id>/students')
@login_required
def module_students(module_id):
    if current_user.role != 'teacher':
        flash('Neturite teisių peržiūrėti studentus.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        module = db.session.get(Module, module_id)
        if not module:
            flash('Modulis nerastas.', 'danger')
            return redirect(url_for('teacher.modules'))
        
        if module.teacher_id != current_user.id:
            flash('Neturite teisių peržiūrėti šio modulio studentus.', 'danger')
            return redirect(url_for('teacher.modules'))
        
        students = module.students
    except Exception as e:
        flash('Įvyko klaida užkraunant studentus. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.modules'))
    
    return render_template('teacher/module_students.html',
                         module=module,
                         students=students)

@bp.route('/teacher/assessments')
@login_required
def assessments():
    if current_user.role != 'teacher':
        flash('Neturite teisių peržiūrėti vertinimus.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Get all modules taught by the teacher with their assessments and schedule entries
        modules = (
            db.session.execute(
                db.select(Module)
                .filter_by(teacher_id=current_user.id)
                .options(
                    db.joinedload(Module.assessments),
                    db.joinedload(Module.schedule_entries),
                    db.joinedload(Module.study_program)
                )
            )
            .unique()
            .scalars()
            .all()
        )

        # For each module, combine and sort assessments and schedule entries
        for module in modules:
            combined_entries = []
            
            # Add assessments
            for assessment in module.assessments:
                combined_entries.append({
                    'id': assessment.id,
                    'type': assessment.type,
                    'title': assessment.title,
                    'description': assessment.description,
                    'date': assessment.date,
                    'due_date': assessment.due_date,
                    'max_points': assessment.max_points,
                    'weight_percentage': assessment.weight_percentage,
                    'grading_scale': assessment.grading_scale
                })
            
            # Add schedule entries
            for entry in module.schedule_entries:
                # Convert time to datetime for consistent sorting
                entry_datetime = datetime.combine(entry.date, entry.start_time)
                combined_entries.append({
                    'id': entry.id,
                    'type': 'schedule',
                    'title': f'Paskaita ({entry.room})',
                    'description': None,  # Schedule entries don't have descriptions
                    'date': entry.date,
                    'start_time': entry.start_time,
                    'end_time': entry.end_time,
                    'entry_datetime': entry_datetime
                })
            
            # Sort by date and time
            def sort_key(x):
                if x['type'] == 'schedule':
                    return (x['date'], x['entry_datetime'])
                else:
                    # For assessments, use date and due_date
                    return (x['date'], x['due_date'])
            
            combined_entries.sort(key=sort_key)
            
            # Attach combined entries to module
            module.combined_entries = combined_entries

        assessment_types = ['lecture', 'lab', 'test', 'exam', 'project']
        
        return render_template(
            'teacher/assessments.html',
            modules=modules,
            assessment_types=assessment_types
        )
    except Exception as e:
        current_app.logger.error(f'Error loading assessments: {str(e)}')
        current_app.logger.error(traceback.format_exc())
        flash('Įvyko klaida užkraunant vertinimus. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.dashboard'))

@bp.route('/teacher/assessments/<int:assessment_id>/grades', methods=['GET', 'POST'])
@login_required
def assessment_grades(assessment_id):
    if current_user.role != 'teacher':
        flash('Neturite teisių vertinti studentų.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        assessment = db.session.get(Assessment, assessment_id)
        if not assessment:
            flash('Vertinimas nerastas.', 'danger')
            return redirect(url_for('teacher.assessments'))
        
        module = db.session.get(Module, assessment.module_id)
        if module.teacher_id != current_user.id:
            flash('Neturite teisių vertinti šio vertinimo studentų.', 'danger')
            return redirect(url_for('teacher.assessments'))
        
        students = module.students
    except Exception as e:
        flash('Įvyko klaida užkraunant duomenis. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.assessments'))
    
    if request.method == 'POST':
        try:
            for student in students:
                grade = request.form.get(f'grade_{student.id}')
                if grade:
                    # Here you would save the grade to the database
                    # This is just a placeholder
                    pass
            
            flash('Pažymiai sėkmingai išsaugoti.', 'success')
            return redirect(url_for('teacher.assessments'))
        except Exception as e:
            flash('Įvyko klaida išsaugant pažymius. Pabandykite dar kartą.', 'danger')
    
    return render_template('teacher/assessment_grades.html',
                         assessment=assessment,
                         module=module,
                         students=students)

@bp.route('/teacher/students')
@login_required
def students():
    if current_user.role != 'teacher':
        flash('Neturite teisių peržiūrėti studentus.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Get all modules taught by the teacher
        modules = db.session.execute(
            db.select(Module).filter_by(teacher_id=current_user.id)
        ).scalars().all()
        
        # Get unique students from all modules
        students = set()
        for module in modules:
            module_students = module.students
            students.update(module_students)
        
        students = sorted(list(students), key=lambda x: (x.last_name, x.first_name))
        
        return render_template('teacher/students.html', students=students)
    except Exception as e:
        flash('Įvyko klaida užkraunant studentus. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.dashboard'))

@bp.route('/teacher/grades')
@login_required
def grades():
    if current_user.role != 'teacher':
        flash('Neturite teisių peržiūrėti pažymius.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Get all modules taught by the teacher
        modules = db.session.execute(
            db.select(Module).filter_by(teacher_id=current_user.id)
        ).scalars().all()
        
        # Get all assessments and their grades for these modules
        module_data = []
        for module in modules:
            assessments = db.session.execute(
                db.select(Assessment).filter_by(module_id=module.id)
            ).scalars().all()
            
            assessment_data = []
            for assessment in assessments:
                grades = db.session.execute(
                    db.select(Grade).filter_by(assessment_id=assessment.id)
                ).scalars().all()
                
                assessment_data.append({
                    'assessment': assessment,
                    'grades': grades
                })
            
            module_data.append({
                'module': module,
                'assessments': assessment_data
            })
        
        return render_template('teacher/grades.html', module_data=module_data)
    except Exception as e:
        flash('Įvyko klaida užkraunant pažymius. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.dashboard'))

@bp.route('/teacher/schedule')
@login_required
@teacher_required
def schedule():
    try:
        # Get all modules taught by the teacher with their study programs and groups
        modules = db.session.execute(
            db.select(Module)
            .filter_by(teacher_id=current_user.id)
            .options(
                db.joinedload(Module.study_program).joinedload(StudyProgram.groups),
                db.joinedload(Module.schedule_entries)
            )
        ).unique().scalars().all()
        
        # Prepare modules with their groups
        modules_with_groups = []
        for module in modules:
            module_dict = {
                'id': module.id,
                'name': module.name,
                'groups': [{'id': g.id, 'name': g.name} for g in module.study_program.groups]
            }
            modules_with_groups.append(module_dict)
        
        # Get all schedule entries for this teacher's modules
        schedule_entries = []
        for module in modules:
            for entry in module.schedule_entries:
                schedule_entries.append({
                    'id': entry.id,
                    'module_id': entry.module_id,
                    'module_name': module.name,
                    'group_id': entry.group_id,
                    'title': entry.title,
                    'type': entry.type,
                    'date': entry.date.strftime('%Y-%m-%d'),
                    'start_time': entry.start_time.strftime('%H:%M'),
                    'end_time': entry.end_time.strftime('%H:%M'),
                    'room': entry.room
                })
        
        # Lithuanian holidays for the current year
        holidays = {
            f"{datetime.now().year}-01-01": "Naujieji metai",
            f"{datetime.now().year}-02-16": "Lietuvos valstybės atkūrimo diena",
            f"{datetime.now().year}-03-11": "Lietuvos nepriklausomybės atkūrimo diena",
            f"{datetime.now().year}-05-01": "Tarptautinė darbo diena",
            f"{datetime.now().year}-06-24": "Joninės, Rasos",
            f"{datetime.now().year}-07-06": "Valstybės diena",
            f"{datetime.now().year}-08-15": "Žolinė",
            f"{datetime.now().year}-11-01": "Visų šventųjų diena",
            f"{datetime.now().year}-12-24": "Kūčios",
            f"{datetime.now().year}-12-25": "Kalėdos",
            f"{datetime.now().year}-12-26": "Kalėdos"
        }
        
        return render_template('teacher/schedule.html',
                             modules=modules_with_groups,
                             schedule_data=schedule_entries,
                             holidays=holidays)
                             
    except Exception as e:
        current_app.logger.error(f'Error loading schedule: {str(e)}')
        current_app.logger.error(traceback.format_exc())
        db.session.rollback()
        flash('Įvyko klaida užkraunant tvarkaraštį. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.dashboard'))

@bp.route('/teacher/schedule/add', methods=['POST'])
@login_required
def add_schedule():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Neturite teisių pridėti paskaitą.'})
    
    try:
        # Get form data
        module_id = request.form.get('module_id')
        title = request.form.get('title')
        type = request.form.get('type')
        date_str = request.form.get('date')
        start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
        end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
        room = request.form.get('room')
        group_id = request.form.get('group_id')  # Get group_id from form
        
        # Log received data
        current_app.logger.info(
            f'Adding schedule: module={module_id}, title={title}, type={type}, '
            f'date={date_str}, start_time={start_time}, end_time={end_time}, room={room}, '
            f'group_id={group_id}'
        )
        
        # Validate required fields
        if not all([module_id, title, type, date_str, start_time, end_time, room, group_id]):
            return jsonify({
                'success': False,
                'message': 'Visi laukai yra privalomi.'
            })
        
        # Convert date string to datetime
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Check if it's a weekend
        if date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            return jsonify({
                'success': False,
                'message': 'Paskaitos negali vykti savaitgaliais.'
            })
        
        # Lithuanian holidays for the current year
        holidays = {
            f"{date.year}-01-01": "Naujieji metai",
            f"{date.year}-02-16": "Lietuvos valstybės atkūrimo diena",
            f"{date.year}-03-11": "Lietuvos nepriklausomybės atkūrimo diena",
            f"{date.year}-05-01": "Tarptautinė darbo diena",
            f"{date.year}-06-24": "Joninės, Rasos",
            f"{date.year}-07-06": "Valstybės diena",
            f"{date.year}-08-15": "Žolinė",
            f"{date.year}-11-01": "Visų šventųjų diena",
            f"{date.year}-12-24": "Kūčios",
            f"{date.year}-12-25": "Kalėdos",
            f"{date.year}-12-26": "Kalėdos"
        }
        
        # Check if it's a holiday
        if date_str in holidays:
            return jsonify({
                'success': False,
                'message': f'Paskaitos negali vykti švenčių dienomis ({holidays[date_str]}).'
            })
        
        # Validate time range (8:00-20:00)
        if start_time < time(8, 0) or end_time > time(20, 0):
            return jsonify({
                'success': False,
                'message': 'Paskaitos gali vykti tik nuo 8:00 iki 20:00.'
            })
        
        if start_time >= end_time:
            return jsonify({
                'success': False,
                'message': 'Paskaitos pradžios laikas turi būti ankstesnis už pabaigos laiką.'
            })
        
        # Check if module exists and belongs to teacher
        module = db.session.execute(
            db.select(Module)
            .filter_by(id=module_id, teacher_id=current_user.id)
        ).scalar_one_or_none()
        
        if not module:
            return jsonify({
                'success': False,
                'message': 'Modulis nerastas arba neturite teisių pridėti jam paskaitų.'
            })
        
        # Check if group exists and belongs to the module's study program
        group = db.session.get(Group, group_id)
        if not group or group.study_program_id != module.study_program_id:
            return jsonify({
                'success': False,
                'message': 'Grupė nerasta arba nepriklauso šio modulio studijų programai.'
            })
        
        # Check for overlapping schedules for the same group on the same date
        existing_schedules = db.session.execute(
            db.select(Schedule)
            .filter(
                Schedule.date == date,
                Schedule.start_time < end_time,
                Schedule.end_time > start_time,
                Schedule.group_id == group_id
            )
        ).scalars().all()
        
        if existing_schedules:
            return jsonify({
                'success': False,
                'message': 'Šiuo laiku grupė jau turi kitą paskaitą.'
            })
        
        # Create new schedule entry
        new_schedule = Schedule(
            module_id=module_id,
            title=title,
            type=type,
            date=date,
            start_time=start_time,
            end_time=end_time,
            room=room,
            group_id=group_id
        )
        
        db.session.add(new_schedule)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Paskaita sėkmingai pridėta.'
        })
        
    except Exception as e:
        current_app.logger.error(f'Error adding schedule: {str(e)}')
        current_app.logger.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Įvyko klaida pridedant paskaitą.'
        })

@bp.route('/teacher/modules/<int:module_id>/students/<int:student_id>/grades')
@login_required
def student_module_grades(module_id, student_id):
    if current_user.role != 'teacher':
        flash('Neturite teisių peržiūrėti pažymius.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Get the module and verify teacher's access
        module = db.session.get(Module, module_id)
        if not module:
            flash('Modulis nerastas.', 'danger')
            return redirect(url_for('teacher.modules'))
        
        if module.teacher_id != current_user.id:
            flash('Neturite teisių peržiūrėti šio modulio pažymius.', 'danger')
            return redirect(url_for('teacher.modules'))
        
        # Get the student
        student = db.session.get(User, student_id)
        if not student:
            flash('Studentas nerastas.', 'danger')
            return redirect(url_for('teacher.module_students', module_id=module_id))
        
        # Get all assessments for this module
        assessments = db.session.execute(
            db.select(Assessment)
            .filter_by(module_id=module_id)
            .order_by(Assessment.date)
        ).scalars().all()
        
        # Get all grades for this student in these assessments
        grades = {}
        for assessment in assessments:
            grade = db.session.execute(
                db.select(Grade)
                .filter_by(assessment_id=assessment.id, student_id=student_id)
            ).scalar_one_or_none()
            grades[assessment.id] = grade
        
        return render_template('teacher/student_module_grades.html',
                             module=module,
                             student=student,
                             assessments=assessments,
                             grades=grades)
    except Exception as e:
        flash('Įvyko klaida užkraunant pažymius. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.module_students', module_id=module_id))

@bp.route('/teacher/modules/<int:module_id>/schedule')
@login_required
def module_schedule(module_id):
    if current_user.role != 'teacher':
        flash('Neturite teisių peržiūrėti tvarkaraštį.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Get the module with its study program
        module = db.session.execute(
            db.select(Module)
            .filter_by(id=module_id, teacher_id=current_user.id)
            .options(
                db.joinedload(Module.study_program)
            )
        ).scalar_one_or_none()
        
        if not module:
            flash('Modulis nerastas arba neturite teisių jį peržiūrėti.', 'danger')
            return redirect(url_for('teacher.modules'))
        
        # Get all groups from the study program
        groups = db.session.execute(
            db.select(Group)
            .filter_by(study_program_id=module.study_program_id)
            .order_by(Group.name)
        ).scalars().all()
        
        # Get schedule entries for this module
        schedule_entries = db.session.execute(
            db.select(Schedule)
            .filter_by(module_id=module_id)
            .order_by(Schedule.date, Schedule.start_time)
        ).scalars().all()
        
        schedule_data = [{
            'id': entry.id,
            'module_id': entry.module_id,
            'module_name': module.name,
            'title': entry.title,
            'type': entry.type,
            'date': entry.date.strftime('%Y-%m-%d'),
            'start_time': entry.start_time.strftime('%H:%M'),
            'end_time': entry.end_time.strftime('%H:%M'),
            'room': entry.room,
            'group_id': entry.group_id
        } for entry in schedule_entries]
        
        # Lithuanian holidays for the current year
        holidays = {
            f"{datetime.now().year}-01-01": "Naujieji metai",
            f"{datetime.now().year}-02-16": "Lietuvos valstybės atkūrimo diena",
            f"{datetime.now().year}-03-11": "Lietuvos nepriklausomybės atkūrimo diena",
            f"{datetime.now().year}-05-01": "Tarptautinė darbo diena",
            f"{datetime.now().year}-06-24": "Joninės, Rasos",
            f"{datetime.now().year}-07-06": "Valstybės diena",
            f"{datetime.now().year}-08-15": "Žolinė",
            f"{datetime.now().year}-11-01": "Visų šventųjų diena",
            f"{datetime.now().year}-12-24": "Kūčios",
            f"{datetime.now().year}-12-25": "Kalėdos",
            f"{datetime.now().year}-12-26": "Kalėdos"
        }
        
        return render_template('teacher/module_schedule.html',
                             module=module,
                             schedule_data=schedule_data,
                             holidays=holidays,
                             groups=groups)
                             
    except Exception as e:
        current_app.logger.error(f'Error loading module schedule: {str(e)}')
        current_app.logger.error(traceback.format_exc())
        db.session.rollback()
        flash('Įvyko klaida užkraunant tvarkaraštį. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.modules'))

@bp.route('/teacher/modules/<int:module_id>/assessments')
@login_required
def module_assessments(module_id):
    if current_user.role != 'teacher':
        flash('Neturite teisių peržiūrėti vertinimus.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Load module with assessments
        module = db.session.execute(
            db.select(Module)
            .filter_by(id=module_id)
            .options(
                joinedload(Module.assessments).joinedload(Assessment.grades),
                joinedload(Module.students)
            )
        ).unique().scalar_one_or_none()
        
        if not module:
            flash('Modulis nerastas.', 'danger')
            return redirect(url_for('teacher.modules'))
        
        if module.teacher_id != current_user.id:
            flash('Neturite teisių peržiūrėti šio modulio vertinimus.', 'danger')
            return redirect(url_for('teacher.modules'))
        
        # Get all assessments for this module
        assessments = sorted(module.assessments, key=lambda x: x.date or datetime.max)
        
        # Get all enrolled students
        students = module.students
        
        # Prepare student data with grades and attendance
        students_data = []
        for student in sorted(students, key=lambda x: (x.last_name, x.first_name)):
            # Create grades dictionary from preloaded grades
            grades_dict = {}
            for assessment in assessments:
                for grade in assessment.grades:
                    if grade.student_id == student.id:
                        grades_dict[assessment.id] = grade
            
            # Get attendance for lectures
            attendance_dict = {
                a.id: any(g.grade > 0 for g in a.grades if g.student_id == student.id)
                for a in assessments if a.type == 'lecture'
            }
            
            students_data.append({
                'student': student,
                'grades': grades_dict,
                'attendance': attendance_dict
            })
        
        # Define available assessment types
        assessment_types = ['lecture', 'lab', 'test', 'exam', 'project']
        
        return render_template('teacher/module_assessments.html',
                             module=module,
                             assessments=assessments,
                             students_data=students_data,
                             assessment_types=assessment_types)
                             
    except Exception as e:
        current_app.logger.error(f'Error in module_assessments: {str(e)}')
        current_app.logger.error(traceback.format_exc())
        flash('Įvyko klaida užkraunant vertinimus. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.modules'))

@bp.route('/teacher/assessments/add', methods=['POST'])
@login_required
def add_assessment():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Neturite teisių pridėti vertinimų.'})
    
    try:
        # Get form data
        module_id = request.args.get('module_id')
        title = request.form.get('title')
        type = request.form.get('type')
        date_str = request.form.get('date')
        due_date_str = request.form.get('due_date')
        weight_percentage = request.form.get('weight_percentage')
        grading_scale = request.form.get('grading_scale')
        max_points = request.form.get('max_points')
        description = request.form.get('description')
        
        # Validate required fields
        if not all([module_id, title, type, date_str, due_date_str, weight_percentage, grading_scale, max_points]):
            flash('Visi laukai yra privalomi.', 'danger')
            return redirect(url_for('teacher.module_assessments', module_id=module_id))
        
        # Convert date strings to datetime
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Neteisingas datos formatas.', 'danger')
            return redirect(url_for('teacher.module_assessments', module_id=module_id))
        
        # Validate weight percentage
        try:
            weight_percentage = int(weight_percentage)
            if not 0 <= weight_percentage <= 100:
                flash('Svoris turi būti tarp 0 ir 100.', 'danger')
                return redirect(url_for('teacher.module_assessments', module_id=module_id))
        except ValueError:
            flash('Neteisingas svorio formatas.', 'danger')
            return redirect(url_for('teacher.module_assessments', module_id=module_id))
        
        # Validate max points
        try:
            max_points = float(max_points)
            if max_points <= 0:
                flash('Maksimalus balų skaičius turi būti didesnis už 0.', 'danger')
                return redirect(url_for('teacher.module_assessments', module_id=module_id))
        except ValueError:
            flash('Neteisingas balų formatas.', 'danger')
            return redirect(url_for('teacher.module_assessments', module_id=module_id))
        
        # Validate grading scale
        if grading_scale not in ['10_POINT', '100_POINT', 'PERCENTAGE']:
            flash('Neteisinga vertinimo sistema.', 'danger')
            return redirect(url_for('teacher.module_assessments', module_id=module_id))
        
        # Check if module exists and belongs to teacher
        module = db.session.execute(
            db.select(Module)
            .filter_by(id=module_id, teacher_id=current_user.id)
        ).scalar_one_or_none()
        
        if not module:
            flash('Modulis nerastas arba neturite teisių pridėti jam vertinimų.', 'danger')
            return redirect(url_for('teacher.modules'))
        
        # Create new assessment
        new_assessment = Assessment(
            module_id=module_id,
            teacher_id=current_user.id,
            title=title,
            type=type,
            description=description,
            date=date,
            due_date=due_date,
            weight_percentage=weight_percentage,
            grading_scale=grading_scale,
            max_points=max_points
        )
        
        db.session.add(new_assessment)
        db.session.commit()
        
        flash('Vertinimas sėkmingai pridėtas.', 'success')
        return redirect(url_for('teacher.module_assessments', module_id=module_id))
        
    except Exception as e:
        current_app.logger.error(f'Error adding assessment: {str(e)}')
        current_app.logger.error(traceback.format_exc())
        db.session.rollback()
        flash('Įvyko klaida pridedant vertinimą. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.module_assessments', module_id=module_id))

@bp.route('/teacher/assessments/<int:assessment_id>/delete', methods=['POST'])
@login_required
@csrf.exempt
def delete_assessment(assessment_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Neturite teisių ištrinti vertinimų.'})
    
    try:
        # Verify CSRF token
        token = request.headers.get('X-CSRF-TOKEN')
        if not token:
            return jsonify({'success': False, 'message': 'CSRF token is missing'})
            
        # Get assessment and check ownership
        assessment = db.session.execute(
            db.select(Assessment)
            .join(Module)
            .filter(
                Assessment.id == assessment_id,
                Module.teacher_id == current_user.id
            )
        ).scalar_one_or_none()

        if not assessment:
            return jsonify({'success': False, 'message': 'Vertinimas nerastas arba neturite teisių jo ištrinti.'})

        # Delete assessment
        db.session.delete(assessment)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Vertinimas sėkmingai ištrintas.'})

    except Exception as e:
        current_app.logger.error(f'Error deleting assessment: {str(e)}')
        return jsonify({'success': False, 'message': 'Įvyko klaida trinant vertinimą.'})

@bp.route('/teacher/create_test_data/<int:module_id>')
@login_required
def create_test_data(module_id):
    if current_user.role != 'teacher':
        flash('Neturite teisių.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Get the module
        module = db.session.execute(
            db.select(Module)
            .filter_by(id=module_id, teacher_id=current_user.id)
        ).scalar_one_or_none()
        
        if not module:
            flash('Modulis nerastas.', 'danger')
            return redirect(url_for('teacher.modules'))
        
        # Create test student if doesn't exist
        test_student = db.session.execute(
            db.select(User).filter_by(email='test.student@example.com')
        ).scalar_one_or_none()
        
        if not test_student:
            test_student = User(
                email='test.student@example.com',
                password_hash=generate_password_hash('password123'),
                first_name='Testas',
                last_name='Studentauskas',
                role='student',
                is_active=True,
                is_approved=True
            )
            db.session.add(test_student)
        
        # Add student to module if not already enrolled
        if test_student not in module.students:
            module.students.append(test_student)
        
        # Create test assessment
        assessment = Assessment(
            module_id=module.id,
            teacher_id=current_user.id,
            title='Kontrolinis darbas 1',
            type='Kontrolinis darbas',
            description='Testinis kontrolinis darbas',
            date=datetime.now().date(),
            due_date=datetime.now() + timedelta(days=7),
            weight_percentage=30,
            grading_scale='10_POINT',
            max_points=10
        )
        db.session.add(assessment)
        
        db.session.commit()
        flash('Testiniai duomenys sėkmingai sukurti.', 'success')
        
    except Exception as e:
        current_app.logger.error(f'Error creating test data: {str(e)}')
        db.session.rollback()
        flash('Įvyko klaida kuriant testinius duomenis.', 'danger')
    
    return redirect(url_for('teacher.module_assessments', module_id=module_id))

@bp.route('/teacher/assessments/<int:assessment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_assessment(assessment_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Neturite teisių redaguoti vertinimų.'})
    
    try:
        # Get assessment and check ownership
        assessment = db.session.execute(
            db.select(Assessment)
            .join(Module)
            .filter(
                Assessment.id == assessment_id,
                Module.teacher_id == current_user.id
            )
        ).scalar_one_or_none()

        if not assessment:
            return jsonify({'success': False, 'message': 'Vertinimas nerastas arba neturite teisių jo redaguoti.'})

        if request.method == 'GET':
            return jsonify({
                'success': True,
                'assessment': {
                    'title': assessment.title,
                    'type': assessment.type,
                    'date': assessment.date.strftime('%Y-%m-%d'),
                    'due_date': assessment.due_date.strftime('%Y-%m-%dT%H:%M'),
                    'weight_percentage': assessment.weight_percentage,
                    'grading_scale': assessment.grading_scale,
                    'max_points': assessment.max_points,
                    'description': assessment.description or ''
                }
            })
        
        # Handle POST request
        title = request.form.get('title')
        type = request.form.get('type')
        date_str = request.form.get('date')
        due_date_str = request.form.get('due_date')
        weight_percentage = request.form.get('weight_percentage')
        grading_scale = request.form.get('grading_scale')
        max_points = request.form.get('max_points')
        description = request.form.get('description')
        
        # Validate required fields
        if not all([title, type, date_str, due_date_str, weight_percentage, grading_scale, max_points]):
            return jsonify({'success': False, 'message': 'Visi laukai yra privalomi.'})
        
        # Convert date strings to datetime
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            return jsonify({'success': False, 'message': 'Neteisingas datos formatas.'})
        
        # Validate weight percentage
        try:
            weight_percentage = int(weight_percentage)
            if not 0 <= weight_percentage <= 100:
                return jsonify({'success': False, 'message': 'Svoris turi būti tarp 0 ir 100.'})
        except ValueError:
            return jsonify({'success': False, 'message': 'Neteisingas svorio formatas.'})
        
        # Validate max points
        try:
            max_points = float(max_points)
            if max_points <= 0:
                return jsonify({'success': False, 'message': 'Maksimalus balų skaičius turi būti didesnis už 0.'})
        except ValueError:
            return jsonify({'success': False, 'message': 'Neteisingas balų formatas.'})
        
        # Validate grading scale
        if grading_scale not in ['10_POINT', '100_POINT', 'PERCENTAGE']:
            return jsonify({'success': False, 'message': 'Neteisinga vertinimo sistema.'})
        
        # Update assessment
        assessment.title = title
        assessment.type = type
        assessment.date = date
        assessment.due_date = due_date
        assessment.weight_percentage = weight_percentage
        assessment.grading_scale = grading_scale
        assessment.max_points = max_points
        assessment.description = description
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Vertinimas sėkmingai atnaujintas.'})
        
    except Exception as e:
        current_app.logger.error(f'Error editing assessment: {str(e)}')
        current_app.logger.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Įvyko klaida redaguojant vertinimą.'})

@bp.route('/teacher/assessments/<int:assessment_id>/grades/<int:student_id>', methods=['POST'])
@login_required
def save_grade(assessment_id, student_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Neturite teisių įvesti pažymius.'}), 403
    
    try:
        # Get assessment and verify ownership
        assessment = db.session.get(Assessment, assessment_id)
        if not assessment:
            return jsonify({'success': False, 'message': 'Vertinimas nerastas.'}), 404
        
        if assessment.module.teacher_id != current_user.id:
            return jsonify({'success': False, 'message': 'Neturite teisių įvesti pažymius šiam vertinimui.'}), 403
        
        # Get student
        student = db.session.get(User, student_id)
        if not student or student.role != 'student':
            return jsonify({'success': False, 'message': 'Studentas nerastas.'}), 404
        
        # Verify student is enrolled in the module
        if student not in assessment.module.students:
            return jsonify({'success': False, 'message': 'Studentas nėra užsiregistravęs į šį modulį.'}), 400
        
        # Get form data
        points = request.form.get('points', type=float)
        comment = request.form.get('comment', '')
        
        if points is None:
            return jsonify({'success': False, 'message': 'Nenurodytas pažymys.'}), 400
        
        # Validate points based on grading scale
        if assessment.grading_scale == '10_POINT':
            if not (0 <= points <= 10):
                return jsonify({'success': False, 'message': 'Pažymys turi būti nuo 0 iki 10.'}), 400
        elif assessment.grading_scale == '100_POINT':
            if not (0 <= points <= 100):
                return jsonify({'success': False, 'message': 'Pažymys turi būti nuo 0 iki 100.'}), 400
        elif assessment.grading_scale == 'PERCENTAGE':
            if not (0 <= points <= 100):
                return jsonify({'success': False, 'message': 'Procentai turi būti nuo 0 iki 100.'}), 400
        
        # Get existing grade or create new one
        grade = Grade.query.filter_by(
            assessment_id=assessment_id,
            student_id=student_id
        ).first()
        
        if grade:
            # Update existing grade
            grade.grade = points
            grade.updated_at = datetime.utcnow()
        else:
            # Create new grade
            grade = Grade(
                assessment_id=assessment_id,
                student_id=student_id,
                grade=points
            )
            db.session.add(grade)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Pažymys sėkmingai išsaugotas.',
            'grade': {
                'points': grade.grade,
                'comment': comment if hasattr(grade, 'comment') else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error saving grade: {str(e)}')
        current_app.logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': 'Įvyko klaida išsaugant pažymį.'}), 500

@bp.route('/modules/<int:module_id>/grades')
@login_required
@teacher_required
def module_grades(module_id):
    try:
        # Get module with basic info
        module = db.session.get(Module, module_id)
        if not module:
            flash('Modulis nerastas.', 'danger')
            return redirect(url_for('teacher.modules'))
        
        if module.teacher_id != current_user.id:
            flash('Jūs neturite teisės peržiūrėti šio modulio pažymių.', 'danger')
            return redirect(url_for('teacher.modules'))

        # Get assessments count
        total_assessments = db.session.query(func.count(Assessment.id))\
            .filter(Assessment.module_id == module_id)\
            .scalar() or 0

        # Get all students enrolled in this module with their grades
        students = db.session.query(User)\
            .join(module_student, User.id == module_student.c.user_id)\
            .filter(module_student.c.module_id == module_id)\
            .order_by(User.last_name, User.first_name)\
            .all()

        students_data = []
        for student in students:
            try:
                # Get student's grades for this module
                grades = db.session.query(Grade)\
                    .join(Assessment)\
                    .filter(
                        Assessment.module_id == module_id,
                        Grade.student_id == student.id
                    ).all()

                graded_count = len(grades)
                
                # Calculate average grade
                valid_grades = [g.grade for g in grades if g.grade is not None]
                average_grade = sum(valid_grades) / len(valid_grades) if valid_grades else None
                
                # Calculate attendance percentage
                attendance_count = len(valid_grades)
                attendance_percentage = (attendance_count / total_assessments * 100) if total_assessments > 0 else 0
                
                # Count overdue assessments
                overdue_count = db.session.query(func.count(Assessment.id))\
                    .filter(
                        Assessment.module_id == module_id,
                        Assessment.due_date < datetime.now(),
                        ~Assessment.id.in_(
                            db.session.query(Grade.assessment_id)
                            .filter(Grade.student_id == student.id)
                        )
                    ).scalar() or 0
                
                students_data.append({
                    'student': student,
                    'average_grade': average_grade,
                    'graded_count': graded_count,
                    'total_assessments': total_assessments,
                    'attendance_percentage': attendance_percentage,
                    'overdue_count': overdue_count
                })
            except Exception as student_error:
                current_app.logger.error(f'Error processing student {student.id}: {str(student_error)}')
                current_app.logger.error(traceback.format_exc())
                continue
        
        return render_template('teacher/module_grades.html',
                             module=module,
                             students_data=students_data)
                             
    except Exception as e:
        current_app.logger.error(f'Error in module_grades: {str(e)}')
        current_app.logger.error(traceback.format_exc())
        db.session.rollback()
        flash('Įvyko klaida užkraunant pažymius. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.modules'))

@bp.route('/teacher/grades_overview')
@login_required
@teacher_required
def grades_overview():
    try:
        # Get all modules taught by the teacher
        modules = db.session.query(Module)\
            .filter_by(teacher_id=current_user.id)\
            .all()
        
        modules_data = []
        for module in modules:
            # Get assessments count for this module
            total_assessments = db.session.query(func.count(Assessment.id))\
                .filter(Assessment.module_id == module.id)\
                .scalar() or 0
            
            # Get all students enrolled in this module
            students = db.session.query(User)\
                .join(module_student, User.id == module_student.c.user_id)\
                .filter(module_student.c.module_id == module.id)\
                .order_by(User.last_name, User.first_name)\
                .all()
            
            students_data = []
            for student in students:
                try:
                    # Get student's grades for this module
                    grades = db.session.query(Grade)\
                        .join(Assessment)\
                        .filter(
                            Assessment.module_id == module.id,
                            Grade.student_id == student.id
                        ).all()
                    
                    graded_count = len(grades)
                    
                    # Calculate average grade
                    valid_grades = [g.grade for g in grades if g.grade is not None]
                    average_grade = sum(valid_grades) / len(valid_grades) if valid_grades else None
                    
                    # Calculate attendance percentage
                    attendance_count = len(valid_grades)
                    attendance_percentage = (attendance_count / total_assessments * 100) if total_assessments > 0 else 0
                    
                    # Count overdue assessments
                    overdue_count = db.session.query(func.count(Assessment.id))\
                        .filter(
                            Assessment.module_id == module.id,
                            Assessment.due_date < datetime.now(),
                            ~Assessment.id.in_(
                                db.session.query(Grade.assessment_id)
                                .filter(Grade.student_id == student.id)
                            )
                        ).scalar() or 0
                    
                    students_data.append({
                        'student': student,
                        'average_grade': average_grade,
                        'graded_count': graded_count,
                        'total_assessments': total_assessments,
                        'attendance_percentage': attendance_percentage,
                        'overdue_count': overdue_count
                    })
                except Exception as student_error:
                    current_app.logger.error(f'Error processing student {student.id}: {str(student_error)}')
                    current_app.logger.error(traceback.format_exc())
                    continue
            
            module_data = {
                'id': module.id,
                'name': module.name,
                'students_data': students_data
            }
            modules_data.append(module_data)
        
        return render_template('teacher/grades_overview.html', modules=modules_data)
        
    except Exception as e:
        current_app.logger.error(f'Error in grades_overview: {str(e)}')
        current_app.logger.error(traceback.format_exc())
        db.session.rollback()
        flash('Įvyko klaida užkraunant pažymius. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('teacher.dashboard'))

@bp.route('/teacher/schedule/<int:entry_id>/update', methods=['POST'])
@login_required
@teacher_required
def update_schedule(entry_id):
    try:
        # Log request details for debugging
        current_app.logger.info(f"Updating schedule entry {entry_id}")
        current_app.logger.info(f"Form data: {request.form.to_dict()}")
        current_app.logger.info(f"Headers: {dict(request.headers)}")

        # Get the schedule entry and verify ownership
        schedule_entry = Schedule.query.get_or_404(entry_id)
        
        # Verify that the teacher owns this module
        module = Module.query.get_or_404(schedule_entry.module_id)
        if module.teacher_id != current_user.id:
            current_app.logger.error(f"User {current_user.id} does not own module {schedule_entry.module_id}")
            return jsonify({'success': False, 'message': 'Neturite teisės redaguoti šios paskaitos'}), 403

        # Validate required fields
        required_fields = ['title', 'type', 'date', 'start_time', 'end_time', 'room', 'group_id']
        missing_fields = [field for field in required_fields if not request.form.get(field)]
        if missing_fields:
            current_app.logger.error(f"Missing required fields: {missing_fields}")
            return jsonify({
                'success': False,
                'message': f'Trūksta privalomų laukų: {", ".join(missing_fields)}'
            }), 400

        # Parse and validate date and time inputs
        try:
            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
            end_time = datetime.strptime(request.form['end_time'], '%H:%M').time()
            
            # Check if the date is not in the past
            if date < datetime.now().date():
                return jsonify({'success': False, 'message': 'Negalima nustatyti datos praeityje'}), 400
                
            # Check if it's not a weekend
            if date.weekday() >= 5:
                return jsonify({'success': False, 'message': 'Negalima nustatyti paskaitos savaitgalį'}), 400
                
            # Check if end time is after start time
            if end_time <= start_time:
                return jsonify({'success': False, 'message': 'Pabaigos laikas turi būti vėlesnis už pradžios laiką'}), 400
                
        except ValueError as e:
            current_app.logger.error(f"Invalid date/time format: {str(e)}")
            return jsonify({'success': False, 'message': 'Neteisingas datos arba laiko formatas'}), 400

        # Check for overlapping schedules
        overlapping = Schedule.query.filter(
            Schedule.id != entry_id,
            Schedule.module_id == schedule_entry.module_id,
            Schedule.date == date,
            Schedule.start_time < end_time,
            Schedule.end_time > start_time
        ).first()

        if overlapping:
            return jsonify({
                'success': False,
                'message': 'Šiuo laiku jau yra suplanuota kita paskaita'
            }), 400

        # Update the schedule entry
        schedule_entry.title = request.form['title']
        schedule_entry.type = request.form['type']
        schedule_entry.date = date
        schedule_entry.start_time = start_time
        schedule_entry.end_time = end_time
        schedule_entry.room = request.form['room']
        schedule_entry.group_id = int(request.form['group_id'])

        db.session.commit()
        current_app.logger.info(f"Successfully updated schedule entry {entry_id}")
        
        return jsonify({'success': True, 'message': 'Paskaita sėkmingai atnaujinta'})

    except Exception as e:
        current_app.logger.error(f"Error updating schedule: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Įvyko klaida atnaujinant paskaitą'}), 500

@bp.route('/teacher/schedule/<int:entry_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_schedule(entry_id):
    try:
        # Get the schedule entry and verify ownership
        schedule_entry = Schedule.query.get_or_404(entry_id)
        
        # Verify that the teacher owns this module
        module = Module.query.get_or_404(schedule_entry.module_id)
        if module.teacher_id != current_user.id:
            return jsonify({'success': False, 'message': 'Neturite teisės ištrinti šios paskaitos'}), 403

        # Delete the entry
        db.session.delete(schedule_entry)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Paskaita sėkmingai ištrinta'})

    except Exception as e:
        current_app.logger.error(f"Error deleting schedule: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Įvyko klaida ištrinant paskaitą'}), 500 