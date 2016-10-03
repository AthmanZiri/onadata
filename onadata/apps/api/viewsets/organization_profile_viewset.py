import json
from django.conf import settings

from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from django.core.mail import send_mail
from django.core.validators import ValidationError

from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import detail_route
from rest_framework.response import Response

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.tools import (get_organization_members,
                                    add_user_to_organization,
                                    remove_user_from_organization,
                                    get_organization_owners_team,
                                    add_user_to_team,
                                    remove_user_from_team)
from onadata.apps.api import permissions
from onadata.libs.filters import (OrganizationPermissionFilter,
                                  OrganizationsSharedWithUserFilter)
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.permissions import ROLES, OwnerRole
from onadata.libs.serializers.organization_serializer import (
    OrganizationSerializer)
from onadata.settings.common import (DEFAULT_FROM_EMAIL, SHARE_ORG_SUBJECT)
from onadata.apps.api.tools import load_class
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.api.tools import _get_owners


BaseViewset = get_baseviewset_class()


def _try_function_org_username(f, organization, username, args=None):
    data = []

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        status_code = status.HTTP_400_BAD_REQUEST
        data = {'username':
                [_(u"User `%(username)s` does not exist."
                   % {'username': username})]}
    else:
        try:
            if args:
                f(organization, user, *args)
            else:
                f(organization, user)
        except ValidationError, e:
            return [unicode(e.message), status.HTTP_400_BAD_REQUEST]

        status_code = status.HTTP_201_CREATED

    return [data, status_code]


def _add_role(org, user, role_cls):
    return role_cls.add(user, org)


def _update_username_role(organization, username, role_cls):
    def _set_organization_role_to_user(org, user, role_cls):
        owners = _get_owners(organization)
        if user in owners and len(owners) <= 1:
            raise ValidationError(_("Organization cannot be without an owner"))
        else:
            role_cls.add(user, organization)

    return _try_function_org_username(_set_organization_role_to_user,
                                      organization,
                                      username,
                                      [role_cls])


def _add_username_to_organization(organization, username):
    return _try_function_org_username(add_user_to_organization,
                                      organization,
                                      username)


def _remove_username_to_organization(organization, username):
    return _try_function_org_username(remove_user_from_organization,
                                      organization,
                                      username)


def _compose_send_email(request, organization, username):
    user = User.objects.get(username=username)

    email_msg = request.data.get('email_msg') \
        or request.query_params.get('email_msg')

    email_subject = request.data.get('email_subject') \
        or request.query_params.get('email_subject')

    if not email_subject:
        email_subject = SHARE_ORG_SUBJECT.format(user.username,
                                                 organization.name)

    # send out email message.
    send_mail(email_subject,
              email_msg,
              DEFAULT_FROM_EMAIL,
              (user.email, ))


def _check_set_role(request, organization, username, required=False):
    """
    Confirms the role and assigns the role to the organization
    """

    role = request.data.get('role')
    role_cls = ROLES.get(role)

    if not role or not role_cls:
        if required:
            message = (_(u"'%s' is not a valid role." % role) if role
                       else _(u"This field is required."))
        else:
            message = _(u"'%s' is not a valid role." % role)

        return status.HTTP_400_BAD_REQUEST, {'role': [message]}
    else:
        data, status_code = _update_username_role(
            organization, username, role_cls)
        if status_code not in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            return (status_code, data)

        owners_team = get_organization_owners_team(organization)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            data = {'username': [_(u"User `%(username)s` does not exist."
                                   % {'username': username})]}

            return (status.HTTP_400_BAD_REQUEST, data)

        # add the owner to owners team
        if role == OwnerRole.name:
            add_user_to_team(owners_team, user)

        if role != OwnerRole.name:
            remove_user_from_team(owners_team, user)

        return (status.HTTP_200_OK, []) if request.method == 'PUT' \
            else (status.HTTP_201_CREATED, [])


def serializer_from_settings():
    if settings.ORG_PROFILE_SERIALIZER:
        return load_class(settings.ORG_PROFILE_SERIALIZER)

    return OrganizationSerializer


class OrganizationProfileViewSet(AuthenticateHeaderMixin,
                                 CacheControlMixin,
                                 ETagsMixin,
                                 ObjectLookupMixin,
                                 BaseViewset,
                                 ModelViewSet):
    """
    List, Retrieve, Update, Create/Register Organizations.
    """
    queryset = OrganizationProfile.objects.all()
    serializer_class = serializer_from_settings()
    lookup_field = 'user'
    permission_classes = [permissions.OrganizationProfilePermissions]
    filter_backends = (OrganizationPermissionFilter,
                       OrganizationsSharedWithUserFilter)

    @detail_route(methods=['DELETE', 'GET', 'POST', 'PUT'])
    def members(self, request, *args, **kwargs):
        organization = self.get_object()
        status_code = status.HTTP_200_OK
        data = []
        username = request.data.get('username') or request.query_params.get(
            'username')

        if request.method in ['DELETE', 'POST', 'PUT'] and not username:
            status_code = status.HTTP_400_BAD_REQUEST
            data = {'username': [_(u"This field is required.")]}
        elif request.method == 'POST':
            data, status_code = _add_username_to_organization(
                organization, username)

            if ('email_msg' in request.data or
                    'email_msg' in request.query_params) \
                    and status_code == 201:
                _compose_send_email(request, organization, username)

            if 'role' in request.data:
                status_code, data = _check_set_role(request,
                                                    organization,
                                                    username)

        elif request.method == 'PUT':
            status_code, data = _check_set_role(request, organization,
                                                username, required=True)

        elif request.method == 'DELETE':
            data, status_code = _remove_username_to_organization(
                organization, username)

        if status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            members = get_organization_members(organization)
            data = [u.username for u in members]
            self.etag_data = json.dumps(data)

        return Response(data, status=status_code)
