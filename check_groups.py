from extensions import db
from models import Group, StudyProgram
from app import create_app

app = create_app()

with app.app_context():
    # Get all study programs
    study_programs = StudyProgram.query.all()
    print("\nStudy Programs:")
    for sp in study_programs:
        print(f"- {sp.name} (ID: {sp.id})")
        
    # Get all groups
    groups = Group.query.all()
    print("\nGroups:")
    for group in groups:
        print(f"- {group.name} (Study Program ID: {group.study_program_id})") 