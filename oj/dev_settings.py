# coding=utf-8
import os
from utils.shortcuts import get_env

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "db",
        "PORT": 5432,
    }
}

REDIS_CONF = {
    "host": get_env("REDIS_HOST", "127.0.0.1"),
    "port": get_env("REDIS_PORT", "6379"),
}


DEBUG = True

ALLOWED_HOSTS = ["*"]

DATA_DIR = f"{BASE_DIR}/data"
