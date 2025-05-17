from flask import Flask, render_template
from config import Config
from extensions import db, login_manager, migrate, bootstrap, csrf
from routes.auth import bp as auth_bp
from routes.admin import bp as admin_bp
from routes.student import bp as student_bp
from routes.teacher import bp as teacher_bp
from routes.main import bp as main_bp
from routes.modules import bp as modules_bp
from models import User
from flask_login import current_user

_is_first_request = True

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bootstrap.init_app(app)
    csrf.init_app(app)
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(modules_bp)
    
    @app.before_request
    def create_admin():
        global _is_first_request
        if _is_first_request:
            _is_first_request = False
            with app.app_context():
                # Patikriname, ar admin vartotojas jau egzistuoja
                admin = User.query.filter_by(email='admin@university.com').first()
                if not admin:
                    admin = User(
                        email='admin@university.com',
                        first_name='Admin',
                        last_name='User',
                        role='admin',
                        is_active=True
                    )
                    admin.set_password('Admin123!')
                    db.session.add(admin)
                    try:
                        db.session.commit()
                        print('Admin vartotojas sukurtas sėkmingai')
                    except Exception as e:
                        db.session.rollback()
                        print(f'Klaida kuriant admin vartotoją: {str(e)}')

    # Context processors
    @app.context_processor
    def utility_processor():
        def get_pending_users_count():
            if current_user.is_authenticated and current_user.role == 'admin':
                return User.query.filter(
                    User.is_approved == False,
                    User.role != 'admin'
                ).count()
            return 0
        
        return {
            'pending_users_count': get_pending_users_count
        }

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True) 
    