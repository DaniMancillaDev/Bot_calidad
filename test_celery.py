import os
import sys
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bot_calidad.settings')
sys.path.append(os.path.join(os.getcwd(), 'web'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings') # wait, bot_calidad or core?
