from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import Module, Assessment, Schedule, User, StudyProgram, module_prerequisite
from forms import ModuleForm, AssessmentForm, ScheduleForm

bp = Blueprint('modules', __name__)

@bp.route('/modules')
@login_required
def list():
    try:
        if current_user.role == 'student':
            modules = current_user.enrolled_modules
        elif current_user.role == 'teacher':
            modules = current_user.teaching_modules
        else:  # admin
            modules = Module.get_all()
    except Exception as e:
        flash('Įvyko klaida užkraunant modulius. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('modules/list.html', modules=modules)

@bp.route('/modules/<int:id>')
@login_required
def details(id):
    try:
        module = Module.get_by_id(id)
        if not module:
            flash('Modulis nerastas.', 'danger')
            return redirect(url_for('modules.list'))
        
        # Get prerequisites
        prerequisites = db.session.execute(
            db.select(Module)
            .join(module_prerequisite, Module.id == module_prerequisite.c.prerequisite_id)
            .where(module_prerequisite.c.module_id == id)
        ).scalars().all()
        
        # Get schedule
        schedule = Schedule.get_by_module(id)
        
        # Get assessments
        assessments = Assessment.get_by_module(id)
    except Exception as e:
        flash('Įvyko klaida užkraunant modulio informaciją. Pabandykite dar kartą.', 'danger')
        return redirect(url_for('modules.list'))
    
    return render_template('modules/details.html',
                         module=module,
                         prerequisites=prerequisites,
                         schedule=schedule,
                         assessments=assessments)

@bp.route('/modules/create', methods=['GET', 'POST'])
@login_required
def create():
    if current_user.role not in ['teacher', 'admin']:
        flash('Neturite teisių kurti modulius.', 'danger')
        return redirect(url_for('modules.list'))
    
    form = ModuleForm()
    try:
        # Get study programs for the form
        study_programs = StudyProgram.get_all()
        form.study_program.choices = [(sp.id, sp.name) for sp in study_programs]
        
        # Get teachers for the form (only for admin)
        if current_user.role == 'admin':
            teachers = db.session.execute(
                db.select(User).where(User.role == 'teacher')
            ).scalars().all()
            form.teacher.choices = [(t.id, f"{t.first_name} {t.last_name}") for t in teachers]
        else:
            form.teacher.data = current_user.id
        
        if form.validate_on_submit():
            module = Module(
                name=form.name.data,
                description=form.description.data,
                credits=form.credits.data,
                semester=form.semester.data,
                study_program_id=form.study_program.data,
                teacher_id=form.teacher.data if current_user.role == 'admin' else current_user.id
            )
            
            if module.save():
                # Add prerequisites
                if form.prerequisites.data:
                    for prerequisite_id in form.prerequisites.data:
                        db.session.execute(
                            module_prerequisite.insert().values(
                                module_id=module.id,
                                prerequisite_id=prerequisite_id
                            )
                        )
                    db.session.commit()
                
                flash('Modulis sėkmingai sukurtas.', 'success')
                return redirect(url_for('modules.details', id=module.id))
            else:
                flash('Įvyko klaida kuriant modulį. Pabandykite dar kartą.', 'danger')
    except Exception as e:
        flash('Įvyko klaida kuriant modulį. Pabandykite dar kartą.', 'danger')
    
    return render_template('modules/create.html', form=form)

@bp.route('/modules/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    try:
        module = Module.get_by_id(id)
        if not module:
            flash('Modulis nerastas.', 'danger')
            return redirect(url_for('modules.list'))
        
        if current_user.role not in ['teacher', 'admin'] or (current_user.role == 'teacher' and module.teacher_id != current_user.id):
            flash('Neturite teisių redaguoti šį modulį.', 'danger')
            return redirect(url_for('modules.list'))
        
        form = ModuleForm(obj=module)
        
        # Get study programs for the form
        study_programs = StudyProgram.get_all()
        form.study_program.choices = [(sp.id, sp.name) for sp in study_programs]
        
        # Get teachers for the form (only for admin)
        if current_user.role == 'admin':
            teachers = db.session.execute(
                db.select(User).where(User.role == 'teacher')
            ).scalars().all()
            form.teacher.choices = [(t.id, f"{t.first_name} {t.last_name}") for t in teachers]
        
        if form.validate_on_submit():
            module.name = form.name.data
            module.description = form.description.data
            module.credits = form.credits.data
            module.semester = form.semester.data
            module.study_program_id = form.study_program.data
            if current_user.role == 'admin':
                module.teacher_id = form.teacher.data
            
            # Update prerequisites
            db.session.execute(
                db.delete(module_prerequisite).where(module_prerequisite.c.module_id == module.id)
            )
            if form.prerequisites.data:
                for prerequisite_id in form.prerequisites.data:
                    db.session.execute(
                        module_prerequisite.insert().values(
                            module_id=module.id,
                            prerequisite_id=prerequisite_id
                        )
                    )
            
            if module.save():
                flash('Modulis sėkmingai atnaujintas.', 'success')
                return redirect(url_for('modules.details', id=module.id))
            else:
                flash('Įvyko klaida atnaujinant modulį. Pabandykite dar kartą.', 'danger')
    except Exception as e:
        flash('Įvyko klaida atnaujinant modulį. Pabandykite dar kartą.', 'danger')
    
    return render_template('modules/edit.html', form=form, module=module)

@bp.route('/modules/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    try:
        module = Module.get_by_id(id)
        if not module:
            flash('Modulis nerastas.', 'danger')
            return redirect(url_for('modules.list'))
        
        if current_user.role not in ['teacher', 'admin'] or (current_user.role == 'teacher' and module.teacher_id != current_user.id):
            flash('Neturite teisių ištrinti šį modulį.', 'danger')
            return redirect(url_for('modules.list'))
        
        if module.delete():
            flash('Modulis sėkmingai ištrintas.', 'success')
        else:
            flash('Įvyko klaida ištrinant modulį. Pabandykite dar kartą.', 'danger')
    except Exception as e:
        flash('Įvyko klaida ištrinant modulį. Pabandykite dar kartą.', 'danger')
    
    return redirect(url_for('modules.list'))

@bp.route('/modules/<int:id>/assessments/create', methods=['GET', 'POST'])
@login_required
def create_assessment(id):
    try:
        module = Module.get_by_id(id)
        if not module:
            flash('Modulis nerastas.', 'danger')
            return redirect(url_for('modules.list'))
        
        if current_user.role not in ['teacher', 'admin'] or (current_user.role == 'teacher' and module.teacher_id != current_user.id):
            flash('Neturite teisių kurti vertinimus.', 'danger')
            return redirect(url_for('modules.list'))
        
        form = AssessmentForm()
        if form.validate_on_submit():
            assessment = Assessment(
                name=form.name.data,
                description=form.description.data,
                due_date=form.due_date.data,
                weight=form.weight.data,
                module_id=module.id
            )
            
            if assessment.save():
                flash('Vertinimas sėkmingai sukurtas.', 'success')
                return redirect(url_for('modules.details', id=module.id))
            else:
                flash('Įvyko klaida kuriant vertinimą. Pabandykite dar kartą.', 'danger')
    except Exception as e:
        flash('Įvyko klaida kuriant vertinimą. Pabandykite dar kartą.', 'danger')
    
    return render_template('modules/create_assessment.html', form=form, module=module) 