from flask import Flask

from .config import Config
from .extensions import db, migrate, socketio
from .schema_utils import ensure_legacy_schema


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins="*")
    with app.app_context():
        ensure_legacy_schema()

    from .blueprints.dashboard.routes import bp as dashboard_bp
    from .blueprints.catalog.routes import bp as catalog_bp
    from .blueprints.orders.routes import bp as orders_bp
    from .blueprints.cash.routes import bp as cash_bp
    from .blueprints.users.routes import bp as users_bp
    from .blueprints.mobile.routes import bp as mobile_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(catalog_bp, url_prefix="/catalog")
    app.register_blueprint(orders_bp)
    app.register_blueprint(cash_bp, url_prefix="/cash")
    app.register_blueprint(users_bp)
    app.register_blueprint(mobile_bp)

    @app.cli.command("seed-demo")
    def seed_demo() -> None:
        """Populate the database with sample data for quick demos."""
        from .seed import seed_demo_data

        seed_demo_data()
        print("Demo data loaded.")

    return app
