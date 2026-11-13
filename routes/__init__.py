from .defect_routes import defect_bp
from .prevention_routes import prevention_bp
from .analytics_routes import analytics_bp
from .export_routes import export_bp
from .auth_routes import auth_bp

__all__ = ['defect_bp', 'prevention_bp', 'analytics_bp', 'export_bp', 'auth_bp']
