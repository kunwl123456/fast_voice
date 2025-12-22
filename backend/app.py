from flask import Flask, jsonify

from backend.routes.auth import auth_bp
from backend.routes.tts import tts_bp
from backend.routes.voice_cloning import voice_cloning_bp
from backend.routes.discovery import discovery_bp
from backend.routes.credits import credits_bp


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    @app.get("/health")
    def health_check():
        return jsonify({"status": "ok"})

    # Register blueprints (each feature is isolated by module)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tts_bp, url_prefix="/api/tts")
    app.register_blueprint(voice_cloning_bp, url_prefix="/api/voice-cloning")
    app.register_blueprint(discovery_bp, url_prefix="/api/discovery")
    app.register_blueprint(credits_bp, url_prefix="/api/credits")

    return app


if __name__ == "__main__":
    create_app().run(debug=True)

