from app import create_app, db
from models import User
from werkzeug.security import generate_password_hash

def create_admin_user():
    app = create_app()
    with app.app_context():
        try:
            # Check if admin already exists
            admin = User.get_by_email('admin@university.lt')
            if admin:
                print("Admin user already exists!")
                return
            
            # Create new admin user
            admin = User(
                email='admin@university.lt',
                first_name='Admin',
                last_name='User',
                role='admin',
                is_active=True
            )
            admin.set_password('admin123')  # Set a secure password
            
            # Try to save the user directly
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
            print("Email: admin@university.lt")
            print("Password: admin123")
                
        except Exception as e:
            print(f"Error creating admin user: {str(e)}")
            print("Please check your database connection and configuration.")
            db.session.rollback()

if __name__ == '__main__':
    create_admin_user() 