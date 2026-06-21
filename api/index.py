import sys
import os

# Add root folder to sys.path so imports of app.py and src packages resolve correctly in serverless functions.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
