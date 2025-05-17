from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bootstrap import Bootstrap
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bootstrap = Bootstrap()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Prašome prisijungti norint pasiekti šį puslapį.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(id):
    from models import User
    return User.query.get(int(id)) 