from app import create_app
from models import User
from extensions import db

def update_admin_approval():
    app = create_app()
    with app.app_context():
        # Get all admin users
        admin_users = User.query.filter_by(role='admin').all()
        
        # Update each admin user to be approved
        for user in admin_users:
            user.is_approved = True
        
        # Commit the changes
        db.session.commit()
        print(f"Updated {len(admin_users)} admin users to be approved")

if __name__ == '__main__':
    update_admin_approval() 