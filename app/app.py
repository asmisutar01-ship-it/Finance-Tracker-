import os
from flask import Flask
from flask_mail import Mail
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from database import init_db
from routes import main as main_blueprint

# Global mail object – imported by routes
mail = Mail()

def create_app():
    app = Flask(__name__)

    # Core config
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-secret-key')

    # Flask-Mail (Gmail SMTP)
    app.config['MAIL_SERVER']   = 'smtp.gmail.com'
    app.config['MAIL_PORT']     = 587
    app.config['MAIL_USE_TLS']  = True
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

    # Initialize extensions
    mail.init_app(app)
    init_db(app)

    # Register blueprints
    app.register_blueprint(main_blueprint)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)