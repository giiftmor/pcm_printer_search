from flask import Flask
from config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    from core.auth import init_admin_password
    init_admin_password(app)

    from modules.printer_search.routes import printer_bp
    from modules.idm_lookup.routes import idm_bp
    from modules.grouper.routes import grouper_bp
    from modules.quick_links.routes import links_bp
    from modules.user_lookup import bp as user_lookup_bp

    app.register_blueprint(printer_bp)
    app.register_blueprint(idm_bp)
    app.register_blueprint(grouper_bp)
    app.register_blueprint(links_bp)
    app.register_blueprint(user_lookup_bp)

    from templates.routes import pages_bp
    app.register_blueprint(pages_bp)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
