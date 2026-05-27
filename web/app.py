import os
import yaml
from pathlib import Path
from flask import Flask, render_template


def load_app_config(path='config/app.yaml'):
    raw = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    return raw


def create_app(config_path='config/app.yaml', db_path=None):
    app = Flask(__name__)
    app.config['APP_CONFIG'] = load_app_config(config_path)
    app.config['DB_PATH'] = (db_path
                             or os.environ.get('CURRENT_DATABASE')
                             or app.config['APP_CONFIG']['database']['path'])

    from web.blueprints.knowledge import knowledge_bp
    from web.blueprints.review import review_bp
    from web.blueprints.ai import ai_bp
    from web.blueprints.upload import upload_bp
    from web.blueprints.system import system_bp

    app.register_blueprint(knowledge_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(system_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    return app
