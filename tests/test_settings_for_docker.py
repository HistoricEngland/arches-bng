"""
This is a template for the test settings file for the mariner_app project when using docker/Arches container tool.
Copy the file and remove the .template extension to use it.

"""

import os
import ast

# import from the test_settings.py files in the same folder first


from arches_bng.settings import *
from .test_settings import *


def get_env_variable(var_name: str):
    """Return the value of an environment variable or raise if missing.
    This mirrors the helper in docker settings but avoids cross-imports during tests.
    """
    try:
        return os.environ[var_name]
    except KeyError:
        raise Exception(f"Set the {var_name} environment variable")


DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": get_env_variable("PGDBNAME"),
        "USER": get_env_variable("PGUSERNAME"),
        "PASSWORD": get_env_variable("PGPASSWORD"),
        "HOST": get_env_variable("PGHOST"),
        "PORT": get_env_variable("PGPORT"),
        "POSTGIS_TEMPLATE": "template_postgis",
    }
}

ELASTICSEARCH_HTTP_PORT = ast.literal_eval(get_env_variable("ESPORT"))
ELASTICSEARCH_HOSTS = [
    {
        "scheme": "http",
        "host": get_env_variable("ESHOST"),
        "port": ELASTICSEARCH_HTTP_PORT,
    }
]
