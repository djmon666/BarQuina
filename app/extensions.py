from __future__ import annotations

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
socketio = SocketIO(async_mode="threading")
login_manager = LoginManager()
