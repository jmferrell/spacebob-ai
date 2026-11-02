"""For production servers:  gunicorn --workers 1 --threads 4 wsgi:app"""
from app import create_app

app = create_app()
