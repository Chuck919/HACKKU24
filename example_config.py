import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_default_secret_key')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///default.db')
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', 'your_email@example.com')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', 'your_password')
    MAIL_USE_TLS = bool(os.getenv('MAIL_USE_TLS', True))
    MAIL_USE_SSL = bool(os.getenv('MAIL_USE_SSL', False))
    MEDIASTACK_API_KEY = os.getenv('MEDIASTACK_API_KEY', 'your_API_key')
    
# Example of how this config could be used
config = Config()