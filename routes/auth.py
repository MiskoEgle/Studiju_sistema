from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
from extensions import db
from models import User, StudyProgram, Group
from forms import LoginForm, RegistrationForm, PasswordChangeForm
from config import Config
from sqlalchemy.exc import IntegrityError
from urllib.parse import urlparse

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.force_password_change:
            flash('Privalote pasikeisti slaptažodį.', 'warning')
            return redirect(url_for('auth.change_password'))
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = db.session.execute(
                db.select(User).filter_by(email=form.email.data)
            ).scalar_one_or_none()
            
            if user is None or not user.check_password(form.password.data):
                flash('Neteisingas el. paštas arba slaptažodis.', 'danger')
                return redirect(url_for('auth.login'))
            
            if not user.is_approved:
                flash('Jūsų paskyra dar nepatvirtinta. Palaukite, kol administratorius ją patvirtins.', 'warning')
                return redirect(url_for('auth.login'))
                
            login_user(user, remember=form.remember_me.data)
            
            if user.force_password_change:
                flash('Privalote pasikeisti slaptažodį.', 'warning')
                return redirect(url_for('auth.change_password'))
                
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('main.index')
            return redirect(next_page)
        except Exception as e:
            flash('Įvyko klaida bandant prisijungti. Bandykite dar kartą.', 'danger')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/login.html', title='Prisijungimas', form=form)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    try:
        study_programs = db.session.execute(db.select(StudyProgram)).scalars().all()
        form.study_program.choices = [(sp.id, sp.name) for sp in study_programs]
    except Exception as e:
        flash('Įvyko klaida užkraunant studijų programas.', 'danger')
        return redirect(url_for('main.index'))
    
    if form.validate_on_submit():
        try:
            user = User(
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                role=form.role.data,
                study_program_id=form.study_program.data,
                is_approved=False,
                is_active=True
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            
            flash('Registracija sėkminga! Palaukite, kol administratorius patvirtins jūsų paskyrą.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('Įvyko klaida registruojant vartotoją. Bandykite dar kartą.', 'danger')
    
    return render_template('auth/register.html', title='Registracija', form=form)

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if not current_user.force_password_change and request.method == 'GET':
        return render_template('auth/change_password.html', 
                             form=PasswordChangeForm(),
                             force_change=False)
    
    form = PasswordChangeForm()
    if form.validate_on_submit():
        try:
            if current_user.check_password(form.current_password.data):
                current_user.set_password(form.new_password.data)
                current_user.force_password_change = False
                db.session.commit()
                flash('Slaptažodis sėkmingai pakeistas!', 'success')
                return redirect(url_for('main.index'))
            else:
                flash('Neteisingas dabartinis slaptažodis.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Įvyko klaida keičiant slaptažodį. Pabandykite dar kartą.', 'danger')
    
    return render_template('auth/change_password.html', 
                         form=form,
                         force_change=current_user.force_password_change)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sėkmingai atsijungėte.', 'success')
    return redirect(url_for('auth.login')) 