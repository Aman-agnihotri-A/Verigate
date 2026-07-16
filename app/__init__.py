"""VeriGate Flask application factory."""
from __future__ import annotations
from flask import Flask
from app.config import Config
from app.extensions import init_mongo
from app.health import health_bp
from app.auth_check import auth_check_bp
from app.verification import verification_bp
from app.mis import mis_bp

def create_app(config_object: type[Config] | None = None) -> Flask:
    app=Flask(__name__)
    app.config.from_object(config_object or Config)
    init_mongo(app)
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_check_bp)
    app.register_blueprint(verification_bp)
    app.register_blueprint(mis_bp)
    return app
