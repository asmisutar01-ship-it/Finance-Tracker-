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

    # ✅ FIXED DATABASE INIT
    init_db(app)

    # Register blueprints
    app.register_blueprint(main_blueprint)

    return app