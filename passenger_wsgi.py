"""WSGI entry point selected in cPanel / CloudLinux Setup Python App."""
import os
import sys
from pathlib import Path

application_root = str(Path(__file__).resolve().parent)
if application_root not in sys.path:
    sys.path.insert(0, application_root)
os.environ["DJANGO_SETTINGS_MODULE"] = "config.cpanel"

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

