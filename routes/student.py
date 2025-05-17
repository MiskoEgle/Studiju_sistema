from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from extensions import db
from models import User, Module, Assessment, Grade, Group, Schedule, StudyProgram, module_student, AssessmentSubmission
from forms import ModuleEnrollmentForm
from sqlalchemy.orm import joinedload
from datetime import datetime

bp = Blueprint('student', __name__)

@bp.route('/student')
@login_required
def dashboard():
    if current_user.role != 'student':
        flash('Neturite teisių pasiekti studento skydelį.', 'danger')
        return render_template('index.html')
    
    try:
        modules = Module.query.filter_by(study_program_id=current_user.study_program_id).all()
        assessments = Assessment.query.join(Module).filter(Module.study_program_id == current_user.study_program_id).all()
        grades = Grade.query.filter_by(student_id=current_user.id).all()
    except Exception as e:
        flash('Įvyko klaida užkraunant duomenis. Pabandykite dar kartą.', 'danger')
        return render_template('student/index.html')
    
    return render_template('student/index.html')

@bp.route('/student/modules')
@login_required
def modules():
    if current_user.role != 'student':
        flash('Neturite teisių peržiūrėti modulius.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        modules = Module.get_by_study_program(current_user.study_program_id)
        enrolled_modules = [m for m in modules if m in current_user.enrolled_modules]
    except Exception as e:
        current_app.logger.error(f'Klaida užkraunant modulius: {str(e)}')
        flash('Įvyko klaida užkraunant modulius. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('student/modules.html',
                         modules=modules,
                         enrolled_modules=enrolled_modules)

@bp.route('/student/modules/<int:module_id>/enroll', methods=['POST'])
@login_required
def enroll_module(module_id):
    if current_user.role != 'student':
        flash('Neturite teisių registruotis į modulius.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Get module with study program info
        module = db.session.execute(
            db.select(Module)
            .options(joinedload(Module.study_program))
            .filter_by(id=module_id)
        ).scalar_one_or_none()

        if not module:
            flash('Modulis nerastas.', 'danger')
            return redirect(url_for('student.modules'))
        
        # Check if module belongs to student's study program
        if module.study_program_id != current_user.study_program_id:
            flash(f'Šis modulis priklauso {module.study_program.name} studijų programai, o ne jūsų programai.', 'danger')
            return redirect(url_for('student.modules'))
        
        # Check if already enrolled
        if module in current_user.enrolled_modules:
            flash('Jau esate užsiregistravęs į šį modulį.', 'warning')
            return redirect(url_for('student.modules'))
        
        try:
            # Enroll in module
            current_user.enrolled_modules.append(module)
            db.session.commit()
            flash(f'Sėkmingai užsiregistravote į modulį {module.name}.', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Klaida įrašant į duomenų bazę: {str(e)}')
            flash('Įvyko klaida registruojant į modulį. Pabandykite dar kartą.', 'danger')
            return redirect(url_for('student.modules'))
            
    except Exception as e:
        current_app.logger.error(f'Klaida registruojantis į modulį {module_id}: {str(e)}')
        flash('Įvyko klaida registruojantis į modulį. Pabandykite dar kartą.', 'danger')
    
    return redirect(url_for('student.modules'))

@bp.route('/student/modules/<int:module_id>/drop', methods=['POST'])
@login_required
def drop_module(module_id):
    if current_user.role != 'student':
        flash('Neturite teisių atsisakyti modulių.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        module = db.session.get(Module, module_id)
        if not module:
            flash('Modulis nerastas.', 'danger')
            return redirect(url_for('student.modules'))
        
        if module not in current_user.enrolled_modules:
            flash('Nesate užsiregistravęs į šį modulį.', 'warning')
            return redirect(url_for('student.modules'))
        
        current_user.enrolled_modules.remove(module)
        db.session.commit()
        flash('Sėkmingai atsisakėte modulio.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Klaida atsisakant modulio: {str(e)}')
        flash('Įvyko klaida atsisakant modulio. Pabandykite dar kartą.', 'danger')
    
    return redirect(url_for('student.modules'))

@bp.route('/student/assessments')
@login_required
def assessments():
    if current_user.role != 'student':
        flash('Neturite teisių peržiūrėti vertinimus.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Get all assessments for enrolled modules
        query = (db.select(Assessment, Module)
                .join(Module)
                .join(module_student, Module.id == module_student.c.module_id)
                .filter(module_student.c.user_id == current_user.id)
                .order_by(Assessment.due_date))
        
        current_app.logger.info(f'Getting assessments for student {current_user.id}')
        results = db.session.execute(query).all()
        current_app.logger.info(f'Found {len(results)} assessments')

        # Get student's grades and submissions
        grades = db.session.execute(
            db.select(Grade)
            .filter(Grade.student_id == current_user.id)
        ).scalars().all()
        grades_dict = {g.assessment_id: g for g in grades}

        submissions = db.session.execute(
            db.select(AssessmentSubmission)
            .filter(AssessmentSubmission.student_id == current_user.id)
        ).scalars().all()
        submissions_dict = {s.assessment_id: s for s in submissions}

        # Organize assessments by module
        assessments_by_module = {}
        for assessment, module in results:
            if module.name not in assessments_by_module:
                assessments_by_module[module.name] = []

            grade = grades_dict.get(assessment.id)
            submission = submissions_dict.get(assessment.id)
            
            assessments_by_module[module.name].append({
                'id': assessment.id,
                'title': assessment.title,
                'type': assessment.type,
                'description': assessment.description,
                'due_date': assessment.due_date,
                'weight': assessment.weight_percentage,
                'grade': grade.grade if grade else None,
                'submission': submission is not None,
                'submission_date': submission.submission_date if submission else None,
                'feedback': submission.feedback if submission else None,
                'is_past_due': assessment.due_date < datetime.utcnow()
            })

        current_app.logger.info(f'Successfully organized assessments for {len(assessments_by_module)} modules')
        return render_template('student/assessments.html',
                             assessments_by_module=assessments_by_module,
                             title='Mano vertinimai')
    except Exception as e:
        current_app.logger.error(f'Error loading assessments: {str(e)}', exc_info=True)
        flash('Įvyko klaida užkraunant vertinimus. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('student.dashboard'))

@bp.route('/student/grades')
@login_required
def grades():
    if current_user.role != 'student':
        flash('Neturite teisių peržiūrėti pažymius.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # First get all grades for the student
        grades_query = (db.select(Grade)
                       .filter(Grade.student_id == current_user.id))
        
        current_app.logger.info(f'Getting grades for student {current_user.id}')
        grades = db.session.execute(grades_query).scalars().all()
        current_app.logger.info(f'Found {len(grades)} grades')

        if not grades:
            current_app.logger.info('No grades found for student')
            return render_template('student/grades.html',
                                 grades_by_module={},
                                 title='Mano pažymiai')

        # Get assessment details for these grades
        assessment_ids = [g.assessment_id for g in grades]
        assessments = db.session.execute(
            db.select(Assessment).filter(Assessment.id.in_(assessment_ids))
        ).scalars().all()
        assessments_dict = {a.id: a for a in assessments}

        # Get module details
        module_ids = [a.module_id for a in assessments]
        modules = db.session.execute(
            db.select(Module).filter(Module.id.in_(module_ids))
        ).scalars().all()
        modules_dict = {m.id: m for m in modules}

        # Get submissions if they exist
        submissions = db.session.execute(
            db.select(AssessmentSubmission)
            .filter(
                AssessmentSubmission.student_id == current_user.id,
                AssessmentSubmission.assessment_id.in_(assessment_ids)
            )
        ).scalars().all()
        submissions_dict = {s.assessment_id: s for s in submissions}

        # Group grades by module
        grades_by_module = {}
        for grade in grades:
            assessment = assessments_dict.get(grade.assessment_id)
            if not assessment:
                current_app.logger.error(f'Assessment {grade.assessment_id} not found for grade {grade.id}')
                continue

            module = modules_dict.get(assessment.module_id)
            if not module:
                current_app.logger.error(f'Module {assessment.module_id} not found for assessment {assessment.id}')
                continue

            if module.name not in grades_by_module:
                grades_by_module[module.name] = []

            submission = submissions_dict.get(grade.assessment_id)
            
            grades_by_module[module.name].append({
                'assessment_name': assessment.title,
                'grade': grade.grade,
                'weight': assessment.weight_percentage,
                'feedback': submission.feedback if submission else None,
                'due_date': assessment.due_date
            })

        # Sort modules by name and grades by due date within each module
        for module_grades in grades_by_module.values():
            module_grades.sort(key=lambda x: x['due_date'])
        
        current_app.logger.info(f'Successfully processed grades for {len(grades_by_module)} modules')
        return render_template('student/grades.html',
                             grades_by_module=grades_by_module,
                             title='Mano pažymiai')
                             
    except Exception as e:
        current_app.logger.error(f'Error loading grades: {str(e)}', exc_info=True)
        flash('Įvyko klaida užkraunant pažymius. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('student.dashboard'))

@bp.route('/student/schedule')
@login_required
def schedule():
    if current_user.role != 'student':
        flash('Neturite teisių peržiūrėti tvarkaraštį.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Get student's group and enrolled modules
        student_group = current_user.group
        current_app.logger.info(f'Checking schedule for student {current_user.id} in group {student_group.name if student_group else "None"}')
        
        if not student_group:
            flash('Jūs neturite priskirtos grupės.', 'warning')
            return render_template('student/schedule.html', schedules=[], title='Mano tvarkaraštis')

        # Get schedules for student's group with eager loading
        schedules_query = db.select(Schedule, Module).join(Module).filter(Schedule.group_id == student_group.id)
        current_app.logger.info(f'Schedule query: {str(schedules_query)}')
        
        schedules = db.session.execute(schedules_query).all()
        current_app.logger.info(f'Found {len(schedules)} schedules')

        # Organize schedules by day
        schedules_by_day = {}
        for schedule, module in schedules:
            current_app.logger.debug(f'Processing schedule: Date={schedule.date}, Module={module.name}, Room={schedule.room}')
            day_name = schedule.date.strftime("%A")
            if day_name not in schedules_by_day:
                schedules_by_day[day_name] = []
            schedules_by_day[day_name].append({
                'module_name': module.name,
                'start_time': schedule.start_time.strftime('%H:%M'),
                'end_time': schedule.end_time.strftime('%H:%M'),
                'room': schedule.room,
                'type': schedule.type
            })

        # Log the final schedule structure
        current_app.logger.info(f'Organized schedules by day: {list(schedules_by_day.keys())}')

        return render_template('student/schedule.html',
                             schedules_by_day=schedules_by_day,
                             title='Mano tvarkaraštis',
                             group=student_group)
    except Exception as e:
        current_app.logger.error(f'Error loading schedule: {str(e)}', exc_info=True)
        flash('Įvyko klaida užkraunant tvarkaraštį. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('student.dashboard'))

@bp.route('/student/group')
@login_required
def group():
    if current_user.role != 'student':
        flash('Neturite teisių peržiūrėti grupės informaciją.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        if not current_user.group_id:
            flash('Jūs neturite priskirtos grupės.', 'warning')
            return render_template('student/group.html', 
                                 group=None,
                                 schedules_by_day={},
                                 title='Mano grupė')

        # Get student's group
        group_query = (db.select(Group)
                      .options(
                          joinedload(Group.study_program),
                          joinedload(Group.students),
                          joinedload(Group.study_program).joinedload(StudyProgram.faculty)
                      )
                      .filter(Group.id == current_user.group_id))
        
        current_app.logger.info(f'Getting group info for student {current_user.id}')
        result = db.session.execute(group_query)
        student_group = result.unique().scalar_one_or_none()
        
        if not student_group:
            current_app.logger.error(f'Group {current_user.group_id} not found')
            flash('Grupė nerasta.', 'danger')
            return render_template('student/group.html', 
                                 group=None,
                                 schedules_by_day={},
                                 title='Mano grupė')

        # Get group's schedule
        schedule_query = (db.select(Schedule, Module)
                         .join(Module)
                         .filter(Schedule.group_id == student_group.id)
                         .order_by(Schedule.date, Schedule.start_time))
        
        current_app.logger.info(f'Getting schedule for group {student_group.id}')
        schedules = db.session.execute(schedule_query).all()
        current_app.logger.info(f'Found {len(schedules)} schedule entries')

        # Organize schedules by day
        schedules_by_day = {}
        for schedule, module in schedules:
            day_name = schedule.date.strftime("%A")
            if day_name not in schedules_by_day:
                schedules_by_day[day_name] = []
            schedules_by_day[day_name].append({
                'module_name': module.name,
                'start_time': schedule.start_time.strftime('%H:%M'),
                'end_time': schedule.end_time.strftime('%H:%M'),
                'room': schedule.room,
                'type': schedule.type
            })

        current_app.logger.info(f'Successfully organized schedules for {len(schedules_by_day)} days')
        return render_template('student/group.html',
                             group=student_group,
                             schedules_by_day=schedules_by_day,
                             title='Mano grupė')
    except Exception as e:
        current_app.logger.error(f'Error loading group info: {str(e)}', exc_info=True)
        flash('Įvyko klaida užkraunant grupės informaciją. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('student.dashboard')) 