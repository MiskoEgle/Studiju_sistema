from app import create_app, db
from flask_migrate import upgrade
from sqlalchemy import text

def clean_database():
    app = create_app()
    with app.app_context():
        # Drop all tables including alembic_version
        with db.engine.connect() as conn:
            # Disable foreign key checks
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            
            # Get all tables
            result = conn.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result]
            
            # Drop all tables
            for table in tables:
                # Quote table names to handle reserved words
                conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
            
            # Re-enable foreign key checks
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            conn.commit()
        
        # Create all tables fresh
        db.create_all()
        
        # Initialize migration
        upgrade()

if __name__ == '__main__':
    clean_database() 