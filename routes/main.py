from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from extensions import db
from models import User, Module, StudyProgram, Group
import os
from werkzeug.utils import secure_filename

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if current_user.is_authenticated:
        try:
            if current_user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif current_user.role == 'teacher':
                return redirect(url_for('teacher.dashboard'))
            elif current_user.role == 'student':
                return redirect(url_for('student.dashboard'))
        except Exception as e:
            flash('Įvyko klaida užkraunant skydelį. Pabandykite dar kartą.', 'danger')
            return render_template('index.html')
    return render_template('index.html')

@bp.route('/profile')
@login_required
def profile():
    try:
        # Get user's modules
        if current_user.is_student:
            modules = current_user.enrolled_modules
        elif current_user.is_teacher:
            modules = current_user.modules
        else:
            modules = []
        
        # Get user's grades
        grades = current_user.grades if current_user.is_student else []
        
        # Get group and study program names safely
        group_name = None
        study_program_name = None
        
        if current_user.group:
            group_name = current_user.group.name
        if current_user.study_program:
            study_program_name = current_user.study_program.name
        
        return render_template('profile/profile.html',
                             user=current_user,
                             modules=modules,
                             grades=grades,
                             group=group_name,
                             study_program=study_program_name)
    except Exception as e:
        print(f"Error in profile route: {str(e)}")  # Print the error for debugging
        flash(f'Įvyko klaida užkraunant profilį: {str(e)}', 'danger')
        return redirect(url_for('main.index'))

@bp.route('/modules')
@login_required
def modules():
    if current_user.role == 'student':
        modules = Module.query.filter_by(study_program_id=current_user.study_program_id).all()
    elif current_user.role == 'teacher':
        modules = Module.query.filter_by(teacher_id=current_user.id).all()
    else:
        modules = Module.query.all()
    
    return render_template('modules/list.html', modules=modules)

@bp.route('/module/<int:module_id>')
@login_required
def module_details(module_id):
    module = Module.query.get_or_404(module_id)
    return render_template('modules/details.html', module=module)

@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        try:
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    # Generate unique filename using timestamp
                    _, ext = os.path.splitext(filename)
                    new_filename = f"profile_{current_user.id}{ext}"
                    
                    # Ensure the uploads directory exists
                    upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'images')
                    if not os.path.exists(upload_path):
                        os.makedirs(upload_path)
                    
                    # Save the file
                    file_path = os.path.join(upload_path, new_filename)
                    file.save(file_path)
                    
                    # Update user profile
                    current_user.profile_picture = new_filename
                    db.session.commit()
                    
                    flash('Profilio nuotrauka sėkmingai atnaujinta.', 'success')
            
            # Update other profile fields if needed
            current_user.first_name = request.form.get('first_name', current_user.first_name)
            current_user.last_name = request.form.get('last_name', current_user.last_name)
            db.session.commit()
            
            flash('Profilis sėkmingai atnaujintas.', 'success')
            return redirect(url_for('main.profile'))
            
        except Exception as e:
            db.session.rollback()
            flash('Įvyko klaida atnaujinant profilį. Pabandykite dar kartą.', 'danger')
    
    return render_template('profile/edit.html', user=current_user) 