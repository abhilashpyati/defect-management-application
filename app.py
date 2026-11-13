import os
from flask import Flask, render_template, jsonify, request
from config import config_by_name
from database.db import close_db, init_db
from routes import defect_bp, prevention_bp, analytics_bp, export_bp, auth_bp

def create_app(config_name=None, config_override=None):
    """
    Application factory for the Defect Management Application.
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__, template_folder='templates', static_folder='static')
    app_config = config_by_name.get(config_name, config_by_name['default'])
    app.config.from_object(app_config)

    if config_override:
        app.config.update(config_override)

    # Register DB teardown
    app.teardown_appcontext(close_db)

    # Auto-initialize database on application startup
    db_path = app.config.get('DATABASE_PATH')
    with app.app_context():
        init_db(db_path, seed_if_empty=True)

    # Register Blueprints
    app.register_blueprint(defect_bp)
    app.register_blueprint(prevention_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(auth_bp)

    # Root route - Serves the web dashboard
    @app.route('/')
    def index():
        return render_template('index.html')

    # Centralized Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'API resource not found.'}), 404
        return render_template('index.html'), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Forbidden: Insufficient role permissions.'}), 403
        return render_template('index.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Internal server error.'}), 500
        return render_template('index.html'), 500

    return app

# WSGI Application instance for Gunicorn / Render
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))
