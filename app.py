from flask import Flask
from cotizacion_controller import cotizacion_bp
from flask_cors import CORS
from database import db
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Permitir HTTP para OAuth2 en desarrollo local
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app = Flask(__name__)
# Set SQLAlchemy config from environment
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "supersecretkey")
print("SECRET_KEY:", repr(app.config["SECRET_KEY"]))

# Configuración de CORS
CORS_ALLOWED_ORIGINS = ["*"]
CORS(app, origins=CORS_ALLOWED_ORIGINS)

app.register_blueprint(cotizacion_bp)
db.init_app(app)

# Crear tablas automáticamente al iniciar el servidor
with app.app_context():
    from models import *

    db.create_all()

import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
)

if __name__ == "__main__":
    app.run(debug=True)
