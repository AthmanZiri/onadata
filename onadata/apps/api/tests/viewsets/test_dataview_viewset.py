import os

from django.conf import settings
from django.test.utils import override_settings
from django.core.cache import cache
from mock import patch

from onadata.libs.permissions import ReadOnlyRole
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.viewer.models.export import Export
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.libs.utils.cache_tools import PROJECT_LINKED_DATAVIEWS
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet


class TestDataViewViewSet(TestAbstractViewSet):

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

        self.view = DataViewViewSet.as_view({
            'post': 'create',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy',
            'get': 'retrieve'
        })

    def test_create_dataview(self):
        self._create_dataview()

    def test_dataview_with_attachment_field(self):
        view = DataViewViewSet.as_view({
            'get': 'data'
        })
        media_file = "test-image.png"
        attachment_file_path = os.path.join(
            settings.PROJECT_ROOT, 'libs', 'tests', "utils", 'fixtures',
            media_file)
        submission_file_path = os.path.join(
            settings.PROJECT_ROOT, 'libs', 'tests', "utils", 'fixtures',
            'tutorial', 'instances', 'uuid10', 'submission.xml')

        # make a submission with an attachment
        with open(attachment_file_path) as f:
            self._make_submission(submission_file_path, media_file=f)

        data = {
            'name': "My DataView",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            # ensure there's an attachment column(photo) in you dataview
            'columns': '["name", "age", "gender", "photo"]'
        }

        self._create_dataview(data=data)
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)
        for a in response.data:
            # retrieve the instance with attachment
            if a.get('photo') == media_file:
                instance_with_attachment = a

        self.assertTrue(instance_with_attachment)
        attachment_info = instance_with_attachment.get('_attachments')[0]
        self.assertEquals(u'image/png', attachment_info.get(u'mimetype'))
        self.assertEquals(
            u'%s/attachments/%s' % (self.user.username, media_file),
            attachment_info.get(u'filename'))
        self.assertEquals(response.status_code, 200)

    def test_get_dataview_form_definition(self):
        self._create_dataview()

        data = {
            "name": "tutorial",
            "title": "tutorial",
            "default_language": "default",
            "id_string": "tutorial",
            "type": "survey",
        }
        self.view = DataViewViewSet.as_view({
            'get': 'form',
        })
        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEquals(response.status_code, 200)

        # JSON format
        response = self.view(request, pk=self.data_view.pk, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(data, response.data)

    def test_get_dataview(self):
        self._create_dataview()

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['dataviewid'], self.data_view.pk)
        self.assertEquals(response.data['name'], 'My DataView')
        self.assertEquals(response.data['xform'],
                          'http://testserver/api/v1/forms/%s' % self.xform.pk)
        self.assertEquals(response.data['project'],
                          'http://testserver/api/v1/projects/%s'
                          % self.project.pk)
        self.assertEquals(response.data['columns'],
                          ["name", "age", "gender"])
        self.assertEquals(response.data['query'],
                          [{"column": "age", "filter": ">", "value": "20"},
                           {"column": "age", "filter": "<", "value": "50"}])
        self.assertEquals(response.data['url'],
                          'http://testserver/api/v1/dataviews/%s'
                          % self.data_view.pk)

    def test_update_dataview(self):
        self._create_dataview()

        data = {
            'name': "My DataView updated",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"age","filter":">","value":"20"}]'
        }

        request = self.factory.put('/', data=data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['name'], 'My DataView updated')

        self.assertEquals(response.data['columns'],
                          ["name", "age", "gender"])

        self.assertEquals(response.data['query'],
                          [{"column": "age", "filter": ">", "value": "20"}])

    def test_patch_dataview(self):
        self._create_dataview()

        data = {
            'name': "My DataView updated",
        }

        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['name'], 'My DataView updated')

    def test_delete_dataview(self):
        self._create_dataview()
        count = DataView.objects.filter(xform=self.xform,
                                        project=self.project).count()

        request = self.factory.delete('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 204)

        after_count = DataView.objects.filter(xform=self.xform,
                                              project=self.project).count()

        self.assertEquals(count - 1, after_count)

    def test_deleted_dataview_not_in_forms_list(self):
        self._create_dataview()
        get_form_request = self.factory.get('/', **self.extra)

        xform_serializer = XFormSerializer(
            self.xform,
            context={'request': get_form_request})

        self.assertIsNotNone(xform_serializer.data['data_views'])

        request = self.factory.delete('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEquals(response.status_code, 204)

        xform_serializer = XFormSerializer(
            self.xform,
            context={'request': get_form_request})

        self.assertEquals(xform_serializer.data['data_views'], [])

    def test_list_dataview(self):
        self._create_dataview()

        data = {
            'name': "My DataView2",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"age","filter":">","value":"20"}]'
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'list',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 2)

    def test_get_dataview_no_perms(self):
        self._create_dataview()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 404)

        # assign alice the perms
        ReadOnlyRole.add(self.user, self.data_view.project)

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)

    def test_dataview_data_filter_integer(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"age","filter":">","value":"20"},'
                     '{"column":"age","filter":"<","value":"50"}]'
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 3)
        self.assertIn("_id", response.data[0])

    def test_dataview_data_filter_date(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "gender", "_submission_time"]',
            'query': '[{"column":"_submission_time",'
                     '"filter":">=","value":"2015-01-01T00:00:00"}]'
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 7)
        self.assertIn("_id", response.data[0])

    def test_dataview_data_filter_string(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "gender", "_submission_time"]',
            'query': '[{"column":"gender","filter":"<>","value":"male"}]'
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 1)

    def test_dataview_data_filter_condition(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "gender", "age"]',
            'query': '[{"column":"name","filter":"=","value":"Fred",'
                     ' "condition":"or"},'
                     '{"column":"name","filter":"=","value":"Kameli",'
                     ' "condition":"or"},'
                     '{"column":"gender","filter":"=","value":"male"}]'
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 2)
        self.assertIn("_id", response.data[0])

    def test_dataview_invalid_filter(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "gender", "age"]',
            'query': '[{"column":"name","filter":"<=>","value":"Fred",'
                     ' "condition":"or"}]'
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          {'query': [u'Filter not supported']})

    def test_dataview_sql_injection(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "gender", "age"]',
            'query': '[{"column":"age","filter":"=",'
                     '"value":"1;UNION ALL SELECT NULL,version()'
                     ',NULL LIMIT 1 OFFSET 1--;"}]'
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          {"detail": u"Error retrieving the data."
                                     u" Check the query parameter"})

    def test_dataview_invalid_columns(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': 'age'
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          {'columns': [u'No JSON object could be decoded']})

    def test_dataview_invalid_query(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["age"]',
            'query': 'age=10'
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          {'query': [u'No JSON object could be decoded']})

    def test_dataview_query_not_required(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["age"]',
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 8)
        self.assertIn("_id", response.data[0])

    def test_csv_export_dataview(self):
        self._create_dataview()
        count = Export.objects.all().count()

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk, format='csv')
        self.assertEqual(response.status_code, 200)

        self.assertEquals(count + 1, Export.objects.all().count())

        headers = dict(response.items())
        self.assertEqual(headers['Content-Type'], 'application/csv')
        content_disposition = headers['Content-Disposition']
        filename = self.filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(ext, '.csv')

        content = self.get_response_content(response)
        test_file_path = os.path.join(settings.PROJECT_ROOT, 'apps',
                                      'viewer', 'tests', 'fixtures',
                                      'dataview.csv')
        with open(test_file_path, 'r') as test_file:
            self.assertEqual(content, test_file.read())

    @override_settings(CELERY_ALWAYS_EAGER=True)
    @patch('onadata.apps.api.viewsets.dataview_viewset.AsyncResult')
    def test_export_csv_dataview_data_async(self, async_result):
        self._create_dataview()
        self._publish_xls_form_to_project()

        view = DataViewViewSet.as_view({
            'get': 'export_async',
        })

        request = self.factory.get('/', data={"format": "csv"},
                                   **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertIsNotNone(response.data)

        self.assertEqual(response.status_code, 202)
        self.assertTrue('job_uuid' in response.data)
        task_id = response.data.get('job_uuid')

        export_pk = Export.objects.all().order_by('pk').reverse()[0].pk

        # metaclass for mocking results
        job = type('AsyncResultMock', (),
                   {'state': 'SUCCESS', 'result': export_pk})
        async_result.return_value = job

        get_data = {'job_uuid': task_id}
        request = self.factory.get('/', data=get_data, **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertIn('export_url', response.data)

        self.assertTrue(async_result.called)
        self.assertEqual(response.status_code, 202)
        export = Export.objects.get(task_id=task_id)
        self.assertTrue(export.is_successful)

    def test_get_charts_data(self):
        self._create_dataview()
        self.view = DataViewViewSet.as_view({
            'get': 'charts',
        })
        request = self.factory.get('/charts', **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)
        data = {'field_name': 'age'}
        request = self.factory.get('/charts', data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'integer')
        self.assertEqual(response.data['field_name'], 'age')
        self.assertEqual(response.data['data_type'], 'numeric')

    def test_geopoint_dataview(self):
        # Dataview with geolocation column selected.
        # -> instances_with_geopoints= True
        data = {
            'name': "My DataView1",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender", "location"]',
            'query': '[{"column":"age","filter":">","value":"20"}]'
        }
        self._create_dataview(data)

        self.assertTrue(self.data_view.instances_with_geopoints)

        # Dataview with geolocation column NOT selected
        # -> instances_with_geopoints= False
        data = {
            'name': "My DataView2",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"age","filter":">","value":"20"}]'
        }
        self._create_dataview(data)

        self.assertFalse(self.data_view.instances_with_geopoints)

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['dataviewid'], self.data_view.pk)
        self.assertEquals(response.data['name'], 'My DataView2')
        self.assertEquals(response.data['instances_with_geopoints'], False)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)

        self.assertNotIn("location", response.data[0])
        self.assertNotIn("_geolocation", response.data[0])

    def test_geopoint_submission_dataview(self):
        data = {
            'name': "My DataView3",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender", "location"]',
            'query': '[{"column":"age","filter":">=","value":"87"}]'
        }
        self._create_dataview(data)

        self.assertTrue(self.data_view.instances_with_geopoints)

        # make submission with geopoint
        path = os.path.join(settings.PROJECT_ROOT, 'libs', 'tests', "utils",
                            'fixtures', 'tutorial', 'instances',
                            'uuid{}'.format(9), 'submission.xml')
        self._make_submission(path)

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['dataviewid'], self.data_view.pk)
        self.assertEquals(response.data['name'], 'My DataView3')
        self.assertEquals(response.data['instances_with_geopoints'], True)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)

        self.assertIn("location", response.data[0])
        self.assertIn("_geolocation", response.data[0])

    def test_dataview_project_cache_cleared(self):
        self._create_dataview()

        view = ProjectViewSet.as_view({
            'get': 'retrieve',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEquals(response.status_code, 200)

        cached_dataviews = cache.get('{}{}'.format(PROJECT_LINKED_DATAVIEWS,
                                                   self.project.pk))

        self.assertIsNotNone(cached_dataviews)

        # update the dataview
        self.data_view.name = "updated name"
        self.data_view.save()

        updated_cache = cache.get('{}{}'.format(PROJECT_LINKED_DATAVIEWS,
                                                self.project.pk))

        self.assertIsNone(updated_cache)

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEquals(response.status_code, 200)

        cached_dataviews = cache.get('{}{}'.format(PROJECT_LINKED_DATAVIEWS,
                                                   self.project.pk))

        self.assertIsNotNone(cached_dataviews)

        self.data_view.delete()

        updated_cache = cache.get('{}{}'.format(PROJECT_LINKED_DATAVIEWS,
                                                self.project.pk))
        self.assertIsNone(updated_cache)

    def test_export_dataview_not_affected_by_normal_exports(self):
        count = Export.objects.all().count()

        view = XFormViewSet.as_view({
            'get': 'retrieve',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.xform.pk, format='csv')
        self.assertEqual(response.status_code, 200)

        self.assertEquals(count+1, Export.objects.all().count())

        self._create_dataview()

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk, format='csv')
        self.assertEqual(response.status_code, 200)

        self.assertEquals(count + 2, Export.objects.all().count())

        headers = dict(response.items())
        self.assertEqual(headers['Content-Type'], 'application/csv')
        content_disposition = headers['Content-Disposition']
        filename = self.filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(ext, '.csv')

        content = self.get_response_content(response)

        # count csv headers and ensure they are three
        self.assertEqual(len(content.split('\n')[0].split(',')), 3)
