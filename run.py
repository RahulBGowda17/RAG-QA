from pathlib import Path
from flask import Flask, send_from_directory
from flask_cors import CORS
from app.config import Config
from app.database import init_db
from app.api import documents_bp, chat_bp, analytics_bp, evaluation_bp, health_bp


def create_app() -> Flask:
    """Application factory for RAG-QA system."""
    Config.ensure_directories()
    init_db()

    static_dir = Path(__file__).resolve().parent / "app" / "static"
    app = Flask(
        __name__,
        static_folder=str(static_dir),
        static_url_path=""
    )
    app.config.from_object(Config)
    CORS(app)

    # Register blueprints
    app.register_blueprint(documents_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(evaluation_bp)
    app.register_blueprint(health_bp)

    # Serve Single Page Application frontend
    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    # Global Error Handlers (safe JSON responses, no Python tracebacks leaked)
    @app.errorhandler(404)
    def not_found(e):
        return {"success": False, "error": "Requested resource not found."}, 404

    @app.errorhandler(413)
    def request_too_large(e):
        return {"success": False, "error": f"File exceeds maximum allowed upload size ({Config.MAX_UPLOAD_SIZE_MB} MB)."}, 413

    @app.errorhandler(500)
    def server_error(e):
        return {"success": False, "error": "An internal server error occurred."}, 500

    return app


if __name__ == "__main__":
    flask_app = create_app()
    print(f"Starting server on http://{Config.HOST}:{Config.PORT} ...", flush=True)
    flask_app.run(host=Config.HOST, port=Config.PORT, debug=False, use_reloader=False)
