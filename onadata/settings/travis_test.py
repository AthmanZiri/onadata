# flake8: noqa
# this preset is used for automated testing of formhub

from common import *  # nopep8

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'onadata_test',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': '127.0.0.1'
    }
}

SECRET_KEY = 'mlfs33^s1l4xf6a36$0#j%dd*sisfoi&)&4s-v=91#^l01v)*j'

JWT_SECRET_KEY = 'thesecretkey'
JWT_ALGORITHM = 'HS256'

if len(sys.argv) >= 2 and (sys.argv[1] == "test" or sys.argv[1] == "test_all"):
    # This trick works only when we run tests from the command line.
    TESTING_MODE = True
else:
    TESTING_MODE = False

if TESTING_MODE:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'test_media/')
    subprocess.call(["rm", "-r", MEDIA_ROOT])
    # need to have CELERY_ALWAYS_EAGER True and BROKER_BACKEND as memory
    # to run tasks immediately while testing
    CELERY_ALWAYS_EAGER = True
    BROKER_BACKEND = 'memory'
    ENKETO_API_TOKEN = 'abc'
else:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media/')

PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)

DEBUG = False
TEMPLATES[0]['OPTIONS']['debug'] = DEBUG
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # 'django.middleware.locale.LocaleMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'onadata.libs.utils.middleware.HTTPResponseNotAllowedMiddleware',
)
