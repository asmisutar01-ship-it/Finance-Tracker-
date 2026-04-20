import os
from flask import Flask
from flask_mail import Mail
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import sys
# Add the parent directory (project root) to sys.path so 'app' is recognized as a package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.routes import main as main_blueprint

# Global mail object – imported by routes
mail = Mail()

def create_app():
    app = Flask(__name__)

    # Core config
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-secret-key')

    # Flask-Mail config
    app.config['MAIL_SERVER']   = 'smtp.gmail.com'
    app.config['MAIL_PORT']     = 587
    app.config['MAIL_USE_TLS']  = True
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

    # Initialize extensions
    mail.init_app(app)

    # Register blueprints
    app.register_blueprint(main_blueprint)

    return app

# Initialize globally for Gunicorn
app = create_app()

if __name__ == "__main__":
    # Ensure port binding works correctly in various environments
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)