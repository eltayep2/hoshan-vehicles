"""
PythonAnywhere WSGI configuration for Hoshan Vehicles Management System
"""

import sys
import os

# Add your project directory to the sys.path
project_home = '/home/YOUR_USERNAME/project-vehicles-management'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variable for production
os.environ['FLASK_ENV'] = 'production'

# Import Flask app
from app import app as application

# Application is ready
if __name__ == '__main__':
    application.run()
