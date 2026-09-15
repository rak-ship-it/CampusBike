"""Start the single-process WSGI server used by the release."""
import os
from app import app
from waitress import serve

if __name__ == '__main__':
    serve(app,host='0.0.0.0',port=int(os.environ.get('PORT','5000')),threads=4)
