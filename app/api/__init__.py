"""API blueprints package."""
from app.api.documents_api import documents_bp
from app.api.chat_api import chat_bp
from app.api.analytics_api import analytics_bp
from app.api.evaluation_api import evaluation_bp
from app.api.health_api import health_bp

__all__ = ["documents_bp", "chat_bp", "analytics_bp", "evaluation_bp", "health_bp"]
