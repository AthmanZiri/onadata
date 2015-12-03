import jwt
from django.conf import settings
from django.core.signing import BadSignature
from django.db import DataError
from django.utils import timezone
from django.utils.translation import ugettext as _
from django_digest import HttpDigestAuthenticator
from django.shortcuts import get_object_or_404
from rest_framework import exceptions
from rest_framework.authentication import get_authorization_header
from rest_framework.authentication import BaseAuthentication
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.authtoken.models import Token

from onadata.apps.api.models.temp_token import TempToken
from onadata.libs.utils.common_tags import API_TOKEN


def expired(time_token_created):
    """Checks if the time between when time_token_created and current time
    is greater than the token expiry time.

    :params time_token_created: The time the token we are checking was created.
    :returns: Boolean True if not passed expired time, otherwise False.
    """
    time_diff = (timezone.now() - time_token_created).total_seconds()
    token_expiry_time = settings.DEFAULT_TEMP_TOKEN_EXPIRY_TIME

    return True if time_diff > token_expiry_time else False


class DigestAuthentication(BaseAuthentication):

    def __init__(self):
        self.authenticator = HttpDigestAuthenticator()

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'digest':
            return None

        try:
            if self.authenticator.authenticate(request):
                return request.user, None
            else:
                raise AuthenticationFailed(
                    _(u"Invalid username/password"))
        except (ValueError, DataError) as e:
            raise AuthenticationFailed(e.message)

    def authenticate_header(self, request):
        response = self.authenticator.build_challenge_response()

        return response['WWW-Authenticate']


class TempTokenAuthentication(TokenAuthentication):
    model = TempToken

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'temptoken':
            return None

        if len(auth) == 1:
            m = _(u'Invalid token header. No credentials provided.')
            raise exceptions.AuthenticationFailed(m)
        elif len(auth) > 2:
            m = _(u'Invalid token header. '
                  'Token string should not contain spaces.')
            raise exceptions.AuthenticationFailed(m)

        return self.authenticate_credentials(auth[1])

    def authenticate_credentials(self, key):
        try:
            token = self.model.objects.get(key=key)
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_(u'Invalid token'))

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed(
                _(u'User inactive or deleted'))

        if expired(token.created):
            raise exceptions.AuthenticationFailed(_(u'Token expired'))

        return (token.user, token)

    def authenticate_header(self, request):
        return 'TempToken'


class EnketoTokenAuthentication(TokenAuthentication):
    model = Token

    def authenticate(self, request):
        try:
            _jwt = request.get_signed_cookie(
                '__enketo', salt=settings.ENKETO_API_SALT)
            jwt_payload = jwt.decode(_jwt,
                                     settings.JWT_SECRET_KEY,
                                     algorithms=[settings.JWT_ALGORITHM])
            api_token = get_object_or_404(
                Token, key=jwt_payload.get(API_TOKEN))

            return api_token.user, api_token
        except BadSignature as e:
            raise exceptions.AuthenticationFailed(_(u'Bad Signature: %s' % e))
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_(u'Invalid token'))
        except KeyError:
            pass
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed(
                _(u'JWT provided doesn\'t have enough segments'))

        return None
