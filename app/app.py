import os
from flask import Flask
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from database import init_db
from routes import main as main_blueprint

def create_app():
    app = Flask(__name__)
    
    # Configure application
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-secret-key')
    
    # Initialize Database
    init_db(app)
    
    # Register Blueprints
    app.register_blueprint(main_blueprint)
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)