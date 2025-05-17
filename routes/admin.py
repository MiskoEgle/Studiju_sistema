from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import User, Faculty, StudyProgram, Group, Module, Assessment, Grade
from forms import UserForm, FacultyForm, StudyProgramForm, GroupForm, ModuleForm, AssessmentForm
from config import Config
import os
from flask import current_app
from functools import wraps
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from datetime import datetime
import random
import string

bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.role == 'admin':
            flash('Neturite teisių pasiekti šį puslapį.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@login_required
def dashboard():
    if current_user.role != 'admin':
        flash('Neturite teisių pasiekti administratoriaus skydelį.', 'danger')
        return render_template('index.html')
    
    try:
        # Collect all necessary data in one try block
        data = {
            'users': User.get_all(),
            'pending_users': User.query.filter_by(is_approved=False).all(),
            'faculties': Faculty.get_all(),
            'study_programs': StudyProgram.get_all(),
            'groups': Group.get_all(),
            'modules': Module.get_all()
        }
        return render_template('admin/index.html', **data)
    except Exception as e:
        current_app.logger.error(f'Klaida užkraunant administratoriaus skydelį: {str(e)}')
        flash('Įvyko klaida užkraunant duomenis. Pabandykite dar kartą.', 'danger')
        return render_template('admin/index.html')

@bp.route('/users')
@login_required
@admin_required
def users():
    try:
        # Get all users
        all_users = db.session.execute(db.select(User)).scalars().all()
        
        # Get pending users
        pending_users = db.session.execute(
            db.select(User).where(
                (User.is_approved.is_(None) | (User.is_approved == False)),
                User.role != 'admin'
            )
        ).scalars().all()
        
        # Filter users by role
        admin_users = [user for user in all_users if user.role == 'admin']
        teacher_users = [user for user in all_users if user.role == 'teacher' and user.is_approved == True]
        student_users = [user for user in all_users if user.role == 'student' and user.is_approved == True]
        
        return render_template('admin/users.html', 
            admin_users=admin_users,
            teacher_users=teacher_users,
            student_users=student_users,
            pending_users=pending_users,
            title='Vartotojų Valdymas'
        )
    except Exception as e:
        flash('Įvyko klaida užkraunant vartotojus.', 'danger')
        return redirect(url_for('admin.dashboard'))

@bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        flash('Neturite teisių kurti vartotojus.', 'danger')
        return redirect(url_for('main.index'))
    
    form = UserForm()
    try:
        # Get study programs and groups with error handling
        study_programs = db.session.execute(db.select(StudyProgram)).scalars().all()
        groups = db.session.execute(db.select(Group)).scalars().all()
        
        # Set form choices with "---" as default option
        form.study_program.choices = [(0, '---')] + [(sp.id, sp.name) for sp in study_programs]
        form.group.choices = [(0, '---')] + [(g.id, g.name) for g in groups]
    except Exception as e:
        flash('Įvyko klaida užkraunant duomenis. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('admin.users'))
    
    if form.validate_on_submit():
        try:
            # Handle study program and group IDs
            study_program_id = form.study_program.data if form.study_program.data != 0 else None
            group_id = form.group.data if form.group.data != 0 else None
            
            user = User(
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                role=form.role.data,
                study_program_id=study_program_id if form.role.data == 'student' else None,
                group_id=group_id if form.role.data == 'student' else None,
                is_approved=form.role.data == 'admin',  # Only admin users are auto-approved
                is_active=True
            )
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.commit()
            flash('Vartotojas sėkmingai sukurtas.', 'success')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash('Įvyko klaida kuriant vartotoją. Pabandykite dar kartą.', 'danger')
    
    return render_template('admin/create_user.html', form=form)

@bp.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.role != 'admin':
        flash('Neturite teisių redaguoti vartotojus.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        user = db.session.execute(
            db.select(User).filter_by(id=id)
        ).scalar_one_or_none()
        
        if not user:
            flash('Vartotojas nerastas.', 'danger')
            return redirect(url_for('admin.users'))
        
        form = UserForm(obj=user)
        
        # Get study programs and groups with error handling
        study_programs = db.session.execute(db.select(StudyProgram)).scalars().all()
        groups = db.session.execute(db.select(Group)).scalars().all()
        
        # Set form choices with "---" as default option
        form.study_program.choices = [(0, '---')] + [(sp.id, sp.name) for sp in study_programs]
        form.group.choices = [(0, '---')] + [(g.id, g.name) for g in groups]
        
        if form.validate_on_submit():
            try:
                user.email = form.email.data
                user.first_name = form.first_name.data
                user.last_name = form.last_name.data
                user.role = form.role.data
                
                # Handle study program and group based on role
                if form.role.data == 'student':
                    user.study_program_id = form.study_program.data if form.study_program.data != 0 else None
                    user.group_id = form.group.data if form.group.data != 0 else None
                else:
                    user.study_program_id = None
                    user.group_id = None
                
                user.is_active = form.is_active.data
                
                # Handle approval status
                if user.role == 'admin':
                    user.is_approved = True  # Admin users are always approved
                else:
                    user.is_approved = form.is_approved.data  # For non-admin users, use the form value
                
                db.session.commit()
                flash('Vartotojas sėkmingai atnaujintas.', 'success')
                return redirect(url_for('admin.users'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Klaida atnaujinant vartotoją: {str(e)}')
                flash('Įvyko klaida atnaujinant vartotoją. Pabandykite dar kartą.', 'danger')
        
        # Set initial values for study program and group
        if user.study_program_id:
            form.study_program.data = user.study_program_id
        if user.group_id:
            form.group.data = user.group_id
        
        return render_template('admin/edit_user.html', form=form, user=user)
    except Exception as e:
        current_app.logger.error(f'Klaida užkraunant vartotojo redagavimo formą: {str(e)}')
        flash('Įvyko klaida užkraunant duomenis. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('admin.users'))

@bp.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(id):
    try:
        user = db.session.execute(
            db.select(User).filter_by(id=id)
        ).scalar_one_or_none()
        
        if not user:
            flash('Vartotojas nerastas.', 'danger')
            return redirect(url_for('admin.users'))
            
        if user.profile_picture:
            try:
                profile_pic_path = os.path.join(current_app.config['UPLOAD_FOLDER'], user.profile_picture)
                if os.path.exists(profile_pic_path):
                    os.remove(profile_pic_path)
            except Exception as e:
                current_app.logger.error(f'Klaida trinant profilio nuotrauką: {str(e)}')
        
        db.session.delete(user)
        db.session.commit()
        flash('Vartotojas sėkmingai ištrintas.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Įvyko klaida trinant vartotoją.', 'danger')
    return redirect(url_for('admin.users'))

@bp.route('/faculties')
@login_required
@admin_required
def faculties():
    try:
        faculties = db.session.execute(db.select(Faculty)).scalars().all()
        return render_template('admin/faculties/index.html', faculties=faculties)
    except Exception as e:
        flash('Įvyko klaida užkraunant fakultetus.', 'danger')
        return redirect(url_for('admin.dashboard'))

@bp.route('/faculties/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_faculty():
    form = FacultyForm()
    if form.validate_on_submit():
        try:
            faculty = Faculty(
                name=form.name.data,
                code=form.code.data,
                description=form.description.data
            )
            db.session.add(faculty)
            db.session.commit()
            flash('Fakultetas sėkmingai sukurtas.', 'success')
            return redirect(url_for('admin.faculties'))
        except Exception as e:
            db.session.rollback()
            flash('Įvyko klaida kuriant fakultetą.', 'danger')
    return render_template('admin/faculties/create.html', form=form)

@bp.route('/faculties/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_faculty(id):
    try:
        faculty = db.session.execute(
            db.select(Faculty).filter_by(id=id)
        ).scalar_one_or_none()
        
        if not faculty:
            flash('Fakultetas nerastas.', 'danger')
            return redirect(url_for('admin.faculties'))
            
        form = FacultyForm(obj=faculty)
        if form.validate_on_submit():
            try:
                faculty.name = form.name.data
                faculty.code = form.code.data
                faculty.description = form.description.data
                db.session.commit()
                flash('Fakultetas sėkmingai atnaujintas.', 'success')
                return redirect(url_for('admin.faculties'))
            except Exception as e:
                db.session.rollback()
                flash('Įvyko klaida atnaujinant fakultetą.', 'danger')
        return render_template('admin/faculties/edit.html', form=form, faculty=faculty)
    except Exception as e:
        flash('Įvyko klaida užkraunant fakultetą.', 'danger')
        return redirect(url_for('admin.faculties'))

@bp.route('/faculties/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_faculty(id):
    try:
        faculty = db.session.execute(
            db.select(Faculty).filter_by(id=id)
        ).scalar_one_or_none()
        
        if not faculty:
            flash('Fakultetas nerastas.', 'danger')
            return redirect(url_for('admin.faculties'))
            
        # Check if faculty has any study programs
        study_programs_count = db.session.execute(
            db.select(func.count()).select_from(StudyProgram).filter_by(faculty_id=id)
        ).scalar()
        
        if study_programs_count > 0:
            flash('Negalima ištrinti fakulteto, nes jis turi studijų programų.', 'danger')
            return redirect(url_for('admin.faculties'))
            
        db.session.delete(faculty)
        db.session.commit()
        flash('Fakultetas sėkmingai ištrintas.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Įvyko klaida trinant fakultetą.', 'danger')
    return redirect(url_for('admin.faculties'))

@bp.route('/study-programs')
@login_required
@admin_required
def study_programs():
    try:
        # Naudojame subquery loading strategiją
        study_programs = db.session.execute(
            db.select(StudyProgram)
            .options(
                joinedload(StudyProgram.faculty),
                joinedload(StudyProgram.students).load_only(User.id),
                joinedload(StudyProgram.modules).load_only(Module.id)
            )
            .order_by(StudyProgram.name)
        ).unique().scalars().all()
        
        # Skaičiuojame studentų ir modulių skaičių atskirai
        for program in study_programs:
            program.student_count = len(program.students)
            program.module_count = len(program.modules)
        
        return render_template('admin/study_programs.html', study_programs=study_programs)
    except Exception as e:
        current_app.logger.error(f'Klaida užkraunant studijų programas: {str(e)}')
        flash('Įvyko klaida užkraunant studijų programas. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('admin.dashboard'))

@bp.route('/study-programs/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_study_program():
    form = StudyProgramForm()
    try:
        # Get faculties for the form
        faculties = db.session.execute(db.select(Faculty)).scalars().all()
        form.faculty_id.choices = [(0, '---')] + [(f.id, f.name) for f in faculties]
        
        if form.validate_on_submit():
            try:
                faculty_id = form.faculty_id.data if form.faculty_id.data != 0 else None
                program = StudyProgram(
                    name=form.name.data,
                    code=form.code.data,
                    faculty_id=faculty_id
                )
                db.session.add(program)
                db.session.commit()
                flash('Studijų programa sėkmingai sukurta.', 'success')
                return redirect(url_for('admin.study_programs'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Klaida kuriant studijų programą: {str(e)}')
                flash('Įvyko klaida kuriant studijų programą. Pabandykite dar kartą.', 'danger')
        return render_template('admin/create_study_program.html', form=form)
    except Exception as e:
        current_app.logger.error(f'Klaida užkraunant studijų programos kūrimo formą: {str(e)}')
        flash('Įvyko klaida užkraunant formą. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('admin.study_programs'))

@bp.route('/study-programs/<int:program_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_study_program(program_id):
    try:
        program = db.session.execute(
            db.select(StudyProgram).filter_by(id=program_id)
        ).scalar_one_or_none()
        
        if not program:
            flash('Studijų programa nerasta.', 'danger')
            return redirect(url_for('admin.study_programs'))
        
        form = StudyProgramForm(obj=program)
        
        # Get faculties for the form
        faculties = db.session.execute(db.select(Faculty)).scalars().all()
        form.faculty_id.choices = [(0, '---')] + [(f.id, f.name) for f in faculties]
        
        if form.validate_on_submit():
            try:
                faculty_id = form.faculty_id.data if form.faculty_id.data != 0 else None
                program.name = form.name.data
                program.code = form.code.data
                program.faculty_id = faculty_id
                
                db.session.commit()
                flash('Studijų programa sėkmingai atnaujinta.', 'success')
                return redirect(url_for('admin.study_programs'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Klaida atnaujinant studijų programą: {str(e)}')
                flash('Įvyko klaida atnaujinant studijų programą. Pabandykite dar kartą.', 'danger')
        
        # Set initial value for faculty
        if program.faculty_id:
            form.faculty_id.data = program.faculty_id
        
        return render_template('admin/edit_study_program.html', form=form, program=program)
    except Exception as e:
        current_app.logger.error(f'Klaida užkraunant studijų programos redagavimo formą: {str(e)}')
        flash('Įvyko klaida užkraunant formą. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('admin.study_programs'))

@bp.route('/study-programs/<int:program_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_study_program(program_id):
    try:
        program = db.session.execute(
            db.select(StudyProgram).filter_by(id=program_id)
        ).scalar_one_or_none()
        
        if not program:
            flash('Studijų programa nerasta.', 'danger')
            return redirect(url_for('admin.study_programs'))
        
        # Check if there are any related records
        if program.students or program.modules:
            flash('Negalima ištrinti studijų programos, nes ji turi susietų studentų arba modulių.', 'danger')
            return redirect(url_for('admin.study_programs'))
        
        db.session.delete(program)
        db.session.commit()
        flash('Studijų programa sėkmingai ištrinta.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Klaida trinant studijų programą: {str(e)}')
        flash('Įvyko klaida trinant studijų programą. Pabandykite dar kartą.', 'danger')
    
    return redirect(url_for('admin.study_programs'))

@bp.route('/groups')
@login_required
@admin_required
def groups():
    try:
        groups = db.session.execute(
            db.select(Group)
            .options(
                joinedload(Group.study_program),
                joinedload(Group.students)
            )
            .order_by(Group.name)
        ).unique().scalars().all()

        study_programs = db.session.execute(
            db.select(StudyProgram)
            .order_by(StudyProgram.name)
        ).scalars().all()

        return render_template(
            'admin/groups.html',
            groups=groups,
            study_programs=study_programs
        )
    except Exception as e:
        current_app.logger.error(f'Klaida užkraunant grupes: {str(e)}')
        flash('Įvyko klaida užkraunant grupes. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('admin.dashboard'))

@bp.route('/groups/create', methods=['GET', 'POST'])
@login_required
def create_group():
    if current_user.role != 'admin':
        flash('Neturite teisių kurti grupes.', 'danger')
        return redirect(url_for('main.index'))
    
    form = GroupForm()
    try:
        # Get study programs using SQLAlchemy 2.0 style
        study_programs = db.session.execute(
            db.select(StudyProgram).order_by(StudyProgram.name)
        ).scalars().all()
        
        # Set form choices with a default empty option
        form.study_program.choices = [(0, '---')] + [(sp.id, sp.name) for sp in study_programs]
        
        if form.validate_on_submit():
            try:
                # Validate study program selection
                if form.study_program.data == 0:
                    flash('Privalote pasirinkti studijų programą.', 'danger')
                    return render_template('admin/create_group.html', form=form)
                
                group = Group(
                    name=form.name.data,
                    year=form.year.data,
                    letter=form.letter.data,
                    study_program_id=form.study_program.data
                )
                db.session.add(group)
                db.session.commit()
                flash('Grupė sėkmingai sukurta.', 'success')
                return redirect(url_for('admin.groups'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Klaida kuriant grupę: {str(e)}')
                flash('Įvyko klaida kuriant grupę. Pabandykite dar kartą.', 'danger')
        
        return render_template('admin/create_group.html', form=form)
    except Exception as e:
        current_app.logger.error(f'Klaida užkraunant duomenis: {str(e)}')
        flash('Įvyko klaida užkraunant duomenis. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('admin.groups'))

@bp.route('/groups/create-auto', methods=['GET'])
@login_required
@admin_required
def create_auto_groups():
    try:
        # Get all students without groups
        students_without_groups = db.session.execute(
            db.select(User).where(
                User.role == 'student',
                User.is_approved == True,
                User.group_id == None
            ).options(
                joinedload(User.study_program).joinedload(StudyProgram.faculty)
            ).order_by(User.study_program_id)
        ).scalars().all()

        if not students_without_groups:
            flash('Nėra studentų be grupių.', 'info')
            return redirect(url_for('admin.groups'))

        current_app.logger.info(f'Rasta {len(students_without_groups)} studentų be grupių')

        # Group students by study program
        students_by_program = {}
        for student in students_without_groups:
            if not student.study_program_id:
                current_app.logger.warning(f'Studentas {student.id} neturi priskirtos studijų programos')
                continue
            
            if student.study_program_id not in students_by_program:
                students_by_program[student.study_program_id] = []
            students_by_program[student.study_program_id].append(student)

        # Get current semester (fall/spring)
        current_month = datetime.now().month
        semester = 'rudens' if 8 <= current_month <= 1 else 'pavasario'
        current_year = datetime.now().year

        groups_created = 0
        students_assigned = 0

        # Create groups for each study program
        for program_id, students in students_by_program.items():
            study_program = db.session.get(StudyProgram, program_id)
            if not study_program:
                current_app.logger.error(f'Nerasta studijų programa su ID {program_id}')
                continue

            faculty = study_program.faculty
            if not faculty:
                current_app.logger.error(f'Studijų programa {program_id} neturi priskirto fakulteto')
                continue

            current_app.logger.info(f'Kuriamos grupės programai {study_program.name} ({len(students)} studentai)')

            # Split students into groups of max 25
            student_groups = [students[i:i + 25] for i in range(0, len(students), 25)]
            
            # Create groups with letters starting from 'A'
            for index, student_group in enumerate(student_groups):
                group_letter = chr(65 + index)  # A, B, C, etc.
                group_name = f"{faculty.code}-{study_program.code}-{str(current_year)[2:]}-{group_letter}-{semester}"
                
                # Check if group already exists
                existing_group = db.session.execute(
                    db.select(Group).filter_by(name=group_name)
                ).scalar_one_or_none()
                
                if existing_group:
                    current_app.logger.warning(f'Grupė {group_name} jau egzistuoja')
                    continue

                # Create new group
                try:
                    new_group = Group(
                        name=group_name,
                        study_program_id=program_id
                    )
                    db.session.add(new_group)
                    db.session.flush()  # Get the group ID
                    
                    # Assign students to the group
                    for student in student_group:
                        student.group_id = new_group.id
                        students_assigned += 1
                    
                    groups_created += 1
                    current_app.logger.info(f'Sukurta grupė {group_name} su {len(student_group)} studentais')
                except Exception as e:
                    current_app.logger.error(f'Klaida kuriant grupę {group_name}: {str(e)}')
                    raise

        db.session.commit()
        flash(f'Sėkmingai sukurtos {groups_created} grupės ir priskirti {students_assigned} studentai.', 'success')
        current_app.logger.info(f'Baigtas grupių kūrimas: {groups_created} grupės, {students_assigned} studentai')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Klaida kuriant grupes: {str(e)}')
        flash('Įvyko klaida kuriant grupes. Patikrinkite ar visi studentai turi priskirtas studijų programas.', 'danger')
    
    return redirect(url_for('admin.groups'))

@bp.route('/assessments')
@login_required
def assessments():
    if current_user.role != 'admin':
        flash('Neturite teisių peržiūrėti vertinimus.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        assessments = Assessment.query.all()
    except Exception as e:
        flash('Įvyko klaida užkraunant vertinimus. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/assessments.html', assessments=assessments)

@bp.route('/assessments/<int:assessment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_assessment(assessment_id):
    if current_user.role != 'admin':
        flash('Neturite teisių redaguoti vertinimus.', 'danger')
        return redirect(url_for('main.index'))
    
    assessment = Assessment.query.get_or_404(assessment_id)
    form = AssessmentForm(obj=assessment)
    
    if form.validate_on_submit():
        try:
            assessment.name = form.name.data
            assessment.description = form.description.data
            assessment.due_date = form.due_date.data
            assessment.weight = form.weight.data
            
            db.session.commit()
            flash('Vertinimas sėkmingai atnaujintas.', 'success')
            return redirect(url_for('admin.assessments'))
        except Exception as e:
            db.session.rollback()
            flash('Įvyko klaida atnaujinant vertinimą. Pabandykite dar kartą.', 'danger')
    
    return render_template('admin/edit_assessment.html', form=form, assessment=assessment)

@bp.route('/assessments/<int:assessment_id>/delete', methods=['POST'])
@login_required
def delete_assessment(assessment_id):
    if current_user.role != 'admin':
        flash('Neturite teisių ištrinti vertinimus.', 'danger')
        return redirect(url_for('main.index'))
    
    assessment = Assessment.query.get_or_404(assessment_id)
    try:
        db.session.delete(assessment)
        db.session.commit()
        flash('Vertinimas sėkmingai ištrintas.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Įvyko klaida ištrinant vertinimą. Pabandykite dar kartą.', 'danger')
    
    return redirect(url_for('admin.assessments'))

@bp.route('/pending-users')
@login_required
@admin_required
def pending_users():
    try:
        # Get all pending users (not approved and not admin)
        pending_users = db.session.execute(
            db.select(User).where(
                User.is_approved == False,
                User.role != 'admin'
            )
        ).scalars().all()
        
        return render_template('admin/pending_users.html', 
            pending_users=pending_users,
            title='Nepatvirtinti Vartotojai'
        )
    except Exception as e:
        flash('Įvyko klaida užkraunant nepatvirtintus vartotojus.', 'danger')
        return redirect(url_for('admin.dashboard'))

@bp.route('/users/approve/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    try:
        user = db.session.execute(
            db.select(User).filter_by(id=user_id)
        ).scalar_one_or_none()
        
        if not user:
            flash('Vartotojas nerastas.', 'danger')
            return redirect(url_for('admin.users'))
            
        if user.role != 'admin':
            user.is_approved = True
            user.is_active = True
            db.session.commit()
            flash(f'Vartotojas {user.email} sėkmingai patvirtintas.', 'success')
        else:
            flash('Administratorių nereikia patvirtinti.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash('Įvyko klaida patvirtinant vartotoją.', 'danger')
    return redirect(url_for('admin.users'))

@bp.route('/users/<int:user_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_user(user_id):
    try:
        user = db.session.execute(
            db.select(User).filter_by(id=user_id)
        ).scalar_one_or_none()
        
        if not user:
            flash('Vartotojas nerastas.', 'danger')
            return redirect(url_for('admin.users'))
            
        if user.profile_picture:
            try:
                profile_pic_path = os.path.join(current_app.config['UPLOAD_FOLDER'], user.profile_picture)
                if os.path.exists(profile_pic_path):
                    os.remove(profile_pic_path)
            except Exception as e:
                current_app.logger.error(f'Klaida trinant profilio nuotrauką: {str(e)}')
        
        db.session.delete(user)
        db.session.commit()
        flash('Vartotojo registracija atmesta.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Įvyko klaida atmetant vartotoją.', 'danger')
    return redirect(url_for('admin.users'))

def generate_temp_password(length=12):
    """Generate a random temporary password"""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(random.choice(characters) for i in range(length))
    # Ensure at least one of each required type
    password = (
        random.choice(string.ascii_lowercase) +
        random.choice(string.ascii_uppercase) +
        random.choice(string.digits) +
        random.choice("!@#$%^&*") +
        ''.join(random.choice(characters) for i in range(length-4))
    )
    return ''.join(random.sample(password, len(password)))  # Shuffle the password

@bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
def reset_user_password(user_id):
    if not current_user.is_admin:
        flash('Neturite teisių atlikti šį veiksmą.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        user = db.session.execute(
            db.select(User).filter_by(id=user_id)
        ).scalar_one_or_none()
        
        if not user:
            flash('Vartotojas nerastas.', 'danger')
            return redirect(url_for('admin.users'))
        
        # Generate new temporary password
        temp_password = generate_temp_password()
        user.set_password(temp_password)
        user.force_password_change = True
        db.session.commit()
        
        flash(f'Slaptažodis sėkmingai atstatytas. Naujas laikinas slaptažodis: {temp_password}', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Klaida atstatant slaptažodį: {str(e)}')
        flash('Įvyko klaida atstatant slaptažodį.', 'danger')
    
    return redirect(url_for('admin.users'))

@bp.route('/groups/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_group(id):
    try:
        group = db.session.execute(
            db.select(Group).filter_by(id=id)
            .options(joinedload(Group.study_program))
        ).scalar_one_or_none()
        
        if not group:
            flash('Grupė nerasta.', 'danger')
            return redirect(url_for('admin.groups'))
            
        form = GroupForm(obj=group)
        
        # Get study programs
        study_programs = db.session.execute(
            db.select(StudyProgram).order_by(StudyProgram.name)
        ).scalars().all()
        
        form.study_program.choices = [(sp.id, sp.name) for sp in study_programs]
        
        if request.method == 'POST':
            try:
                group.name = request.form.get('name')
                group.study_program_id = int(request.form.get('study_program'))
                
                db.session.commit()
                flash('Grupė sėkmingai atnaujinta.', 'success')
                return redirect(url_for('admin.groups'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Klaida atnaujinant grupę: {str(e)}')
                flash('Įvyko klaida atnaujinant grupę. Pabandykite dar kartą.', 'danger')
        
        return render_template('admin/edit_group.html', form=form, group=group)
    except Exception as e:
        current_app.logger.error(f'Klaida užkraunant grupės redagavimo formą: {str(e)}')
        flash('Įvyko klaida užkraunant duomenis. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('admin.groups'))

@bp.route('/groups/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_group(id):
    try:
        group = db.session.execute(
            db.select(Group).filter_by(id=id)
            .options(joinedload(Group.students))
        ).scalar_one_or_none()
        
        if not group:
            flash('Grupė nerasta.', 'danger')
            return redirect(url_for('admin.groups'))
        
        # Check if group has students
        if group.students:
            flash('Negalima ištrinti grupės, nes joje yra studentų.', 'danger')
            return redirect(url_for('admin.groups'))
        
        db.session.delete(group)
        db.session.commit()
        flash('Grupė sėkmingai ištrinta.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Klaida trinant grupę: {str(e)}')
        flash('Įvyko klaida trinant grupę.', 'danger')
    
    return redirect(url_for('admin.groups')) 