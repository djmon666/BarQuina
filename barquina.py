import os

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    host = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_RUN_PORT", os.getenv("PORT", "5000")))
    debug_flag = os.getenv("FLASK_DEBUG", "1") not in {"0", "false", "False"}
    socketio.run(app, host=host, port=port, debug=debug_flag)
