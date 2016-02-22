import os

from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from onadata.apps.logger.models.widget import Widget
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.widget_viewset import WidgetViewSet
from onadata.libs.permissions import ReadOnlyRole


class TestWidgetViewSet(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, 'libs', 'tests', "utils", "fixtures",
            "tutorial.xls")

        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        for x in range(1, 9):
            path = os.path.join(
                settings.PROJECT_ROOT, 'libs', 'tests', "utils", 'fixtures',
                'tutorial', 'instances', 'uuid{}'.format(x), 'submission.xml')
            self._make_submission(path)
            x += 1
        self._create_dataview()

        self.view = WidgetViewSet.as_view({
            'post': 'create',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy',
            'get': 'retrieve',
        })

    def test_create_widget(self):
        self._create_widget()

    def test_create_only_mandatory_fields(self):
        data = {
            'content_object': 'http://testserver/api/v1/forms/%s' %
                              self.xform.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "_submission_time",
        }

        self._create_widget(data)

    def test_create_using_dataview(self):

        data = {
            'content_object': 'http://testserver/api/v1/dataviews/%s' %
                              self.data_view.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "_submission_time",
        }

        self._create_widget(data)

    def test_create_using_unsupported_model_source(self):

        data = {
            'content_object': 'http://testserver/api/v1/projects/%s' %
                              self.project.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "_submission_time",
        }

        count = Widget.objects.all().count()

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(count, Widget.objects.all().count())
        self.assertEquals(
            response.data['content_object'],
            [u"`%s` is not a valid relation." % data['content_object']]
        )

    def test_create_without_required_field(self):

        data = {
            'content_object': 'http://testserver/api/v1/forms/%s' %
                              self.xform.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
        }

        count = Widget.objects.all().count()

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(count, Widget.objects.all().count())
        self.assertEquals(response.data['column'],
                          [u"This field may not be blank."])

    def test_create_unsupported_widget_type(self):

        data = {
            'content_object': 'http://testserver/api/v1/forms/%s' %
                              self.xform.pk,
            'widget_type': "table",
            'view_type': "horizontal-bar",
            'column': "_submission_time",
        }

        count = Widget.objects.all().count()

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(count, Widget.objects.all().count())
        self.assertEquals(response.data['widget_type'],
                          [u"`%s` is not a valid choice."
                           % data['widget_type']])

    def test_update_widget(self):
        self._create_widget()

        key = self.widget.key

        data = {
            'title': 'My new title updated',
            'description': 'new description',
            'aggregation': 'new aggregation',
            'content_object': 'http://testserver/api/v1/forms/%s' %
                              self.xform.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "_submission_time",
        }

        request = self.factory.put('/', data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.widget = Widget.objects.all().order_by('pk').reverse()[0]

        self.assertEquals(key, self.widget.key)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['title'], 'My new title updated')
        self.assertEquals(response.data['key'], key)
        self.assertEquals(response.data['description'],
                          "new description")
        self.assertEquals(response.data['aggregation'],
                          "new aggregation")

    def test_patch_widget(self):
        self._create_widget()

        data = {
            'column': "_submitted_by",
        }

        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['column'], '_submitted_by')

    def test_delete_widget(self):
        ct = ContentType.objects.get(model='xform', app_label='logger')
        self._create_widget()
        count = Widget.objects.filter(content_type=ct,
                                      object_id=self.xform.pk).count()

        request = self.factory.delete('/', **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEquals(response.status_code, 204)

        after_count = Widget.objects.filter(content_type=ct,
                                            object_id=self.xform.pk).count()
        self.assertEquals(count-1, after_count)

    def test_list_widgets(self):
        self._create_widget()
        self._publish_xls_form_to_project()

        data = {
            'content_object': 'http://testserver/api/v1/forms/%s' %
                              self.xform.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "_submitted_by",
        }

        self._create_widget(data=data)

        view = WidgetViewSet.as_view({
            'get': 'list',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 2)

    def test_widget_permission_create(self):
        self._create_widget()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        view = WidgetViewSet.as_view({
            'get': 'list',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 0)

        # assign alice the perms
        ReadOnlyRole.add(self.user, self.xform)

        request = self.factory.get('/', **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 1)

    def test_widget_permission_get(self):
        self._create_widget()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEquals(response.status_code, 404)

        # assign alice the perms
        ReadOnlyRole.add(self.user, self.project)

        request = self.factory.get('/', **self.extra)
        response = self.view(request, formid=self.xform.pk,
                             pk=self.widget.pk)

        self.assertEquals(response.status_code, 200)

    def test_widget_data(self):
        self._create_widget()

        data = {
            "data": True
        }

        request = self.factory.get('/', data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get('data'))
        self.assertEquals(len(response.data.get('data')), 8)
        self.assertIn('age', response.data.get('data')[0])
        self.assertIn('gender', response.data.get('data')[0])
        self.assertIn('count', response.data.get('data')[0])

    def test_widget_data_widget(self):
        data = {
            'content_object': 'http://testserver/api/v1/forms/%s' %
                              self.xform.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "gender",
        }

        self._create_widget(data)

        data = {
            "data": True
        }
        request = self.factory.get('/', data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get('data'))
        self.assertEquals(response.data.get('data'),
                          [{'count': 7, 'gender': u'male'},
                           {'count': 1, 'gender': u'female'}])

    def test_widget_with_key(self):
        self._create_widget()

        view = WidgetViewSet.as_view({
            'get': 'list',
        })

        data = {
            "key": self.widget.key
        }

        request = self.factory.get('/', data=data, **self.extra)
        response = view(request, formid=self.xform.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get('data'))
        self.assertEquals(len(response.data.get('data')), 8)
        self.assertIn('age', response.data.get('data')[0])
        self.assertIn('gender', response.data.get('data')[0])
        self.assertIn('count', response.data.get('data')[0])

    def test_widget_with_key_anon(self):
        self._create_widget()

        view = WidgetViewSet.as_view({
            'get': 'list',
        })

        data = {
            "key": self.widget.key
        }

        # Anonymous user can access the widget
        self.extra = {}

        request = self.factory.get('/', data=data, **self.extra)
        response = view(request, formid=self.xform.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get('data'))
        self.assertEquals(len(response.data.get('data')), 8)
        self.assertIn('age', response.data.get('data')[0])
        self.assertIn('gender', response.data.get('data')[0])
        self.assertIn('count', response.data.get('data')[0])

    def test_widget_with_nonexistance_key(self):
        self._create_widget()

        view = WidgetViewSet.as_view({
            'get': 'list',
        })

        data = {
            "key": "randomkeythatdoesnotexist"
        }

        self.extra = {}

        request = self.factory.get('/', data=data, **self.extra)
        response = view(request, pk=self.xform.pk)

        self.assertEqual(response.status_code, 404)

    def test_widget_data_public_form(self):
        self._create_widget()

        view = WidgetViewSet.as_view({
            'get': 'list',
        })
        self.extra = {}

        request = self.factory.get('/', **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEquals(len(response.data), 0)

        # Anonymous user can access widget in public form
        self.xform.shared_data = True
        self.xform.save()

        request = self.factory.get('/', **self.extra)
        response = view(request, formid=self.xform.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEquals(len(response.data), 1)

    def test_widget_pk_formid_required(self):
        self._create_widget()

        data = {
            'title': 'My new title updated',
            'description': 'new description',
            'content_object': 'http://testserver/api/v1/forms/%s' %
                              self.xform.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "_submission_time",
        }

        request = self.factory.put('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          {u'detail': u"'pk' required for this"
                           u" action"})

    def test_list_widgets_with_formid(self):
        self._create_widget()
        self._publish_xls_form_to_project()

        data = {
            'content_object': 'http://testserver/api/v1/forms/%s' %
                              self.xform.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "_submitted_by",
        }

        self._create_widget(data=data)

        view = WidgetViewSet.as_view({
            'get': 'list',
        })

        data = {
            "xform": self.xform.pk
        }

        request = self.factory.get('/', data=data, **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 1)

    def test_create_column_not_in_form(self):
        data = {
            'content_object': 'http://testserver/api/v1/forms/%s' %
                              self.xform.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "doesnotexists",
        }

        count = Widget.objects.all().count()

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(count, Widget.objects.all().count())
        self.assertEquals(response.data['column'],
                          [u"'doesnotexists' not in the form."])

    def test_create_widget_with_xform_no_perms(self):
        data = {
            'content_object': 'http://testserver/api/v1/forms/%s' %
                              self.xform.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "age",
        }

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data['content_object'],
                          [u"You don't have permission to the XForm."])

    def test_filter_widgets_by_dataview(self):
        self._create_widget()
        self._publish_xls_form_to_project()

        data = {
            'content_object': 'http://testserver/api/v1/dataviews/%s' %
                              self.data_view.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "_submitted_by",
        }

        self._create_widget(data=data)

        data = {
            'content_object': 'http://testserver/api/v1/dataviews/%s' %
                              self.data_view.pk,
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "_submission_time",
        }

        self._create_widget(data)

        view = WidgetViewSet.as_view({
            'get': 'list',
        })

        data = {
            "dataview": self.data_view.pk
        }

        request = self.factory.get('/', data=data, **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 2)

        data = {
            "dataview": "so_invalid"
        }

        request = self.factory.get('/', data=data, **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data['detail'],
                          u"Invalid value for dataview %s." % "so_invalid")

    def test_order_widget(self):
        self._create_widget()
        self._create_widget()
        self._create_widget()

        data = {
            'column': "_submission_time",
            'order': 1
        }

        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, pk=self.widget.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['order'], 1)

        widget = Widget.objects.all().order_by('pk')[0]
        self.assertEquals(widget.order, 0)

        widget = Widget.objects.all().order_by('pk')[1]
        self.assertEquals(widget.order, 2)
