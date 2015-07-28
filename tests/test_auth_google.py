"""Test code for iiif.auth_google

See http://flask.pocoo.org/docs/0.10/testing/ for Flask notes
"""
from flask import Flask, request, make_response, redirect
from werkzeug.datastructures import Headers
import json
import mock
import re
import unittest

from iiif.auth_google import IIIFAuthGoogle

dummy_app = Flask('dummy')

# test client_secret_file
csf = 'tests/testdata/test_client_secret.json'


class Struct(object):
    """Class with properties created from **kwargs"""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Readable(object):
    """Class supporting read() method to mock urllib2.urlopen"""
    def __init__(self,value):
        self.value = value
    def read(self):
        return self.value


class TestAll(unittest.TestCase):

    def setUp(self):
        self.app = dummy_app.test_client()

    def tearDown(self):
        pass

    def test01_init(self):
        auth = IIIFAuthGoogle(client_secret_file=csf)
        self.assertTrue( re.match(r'\d+_',auth.cookie_prefix) )
        auth = IIIFAuthGoogle(client_secret_file=csf, cookie_prefix='abc')
        self.assertEqual( auth.cookie_prefix, 'abc' )
        self.assertEqual( auth.google_api_client_id, 'SECRET_CODE_537' )
        auth = IIIFAuthGoogle(client_secret_file='/does_not_exist', cookie_prefix='abcd')
        self.assertEqual( auth.cookie_prefix, 'abcd' )
        self.assertEqual( auth.google_api_client_id, 'oops_missing_client_id' )

    def test02_logout_service_description(self):
        auth = IIIFAuthGoogle(client_secret_file=csf)
        auth.logout_uri = 'xyz'
        lsd = auth.logout_service_description()
        self.assertEqual( lsd['profile'], 'http://iiif.io/api/auth/0/logout' )
        self.assertEqual( lsd['@id'], 'xyz' )
        self.assertEqual( lsd['label'], 'Logout from image server' )

    def test03_info_authn(self):
        with dummy_app.test_request_context('/a_request'):
            auth = IIIFAuthGoogle(client_secret_file=csf)
            ia = auth.info_authn()
            self.assertEqual( ia, False )

    def test04_image_authn(self):
        with dummy_app.test_request_context('/a_request'):
            auth = IIIFAuthGoogle(client_secret_file=csf)
            ia = auth.image_authn()
            self.assertEqual( ia, '' )

    def test05_login_handler(self):
        with dummy_app.test_request_context('/a_request'):
            config = Struct(host='a_host',port=None)
            auth = IIIFAuthGoogle(client_secret_file=csf)
            response = auth.login_handler(config=config,prefix='wxy')
            self.assertEqual( response.status_code, 302 )
            self.assertEqual( response.headers['Content-type'], 'text/html; charset=utf-8' )
            self.assertTrue( re.match(r'https://accounts.google.com/o/oauth2/auth', response.headers['Location']) )
            html = response.get_data()
            self.assertTrue( re.search('<h1>Redirecting...</h1>',html) )
 
    def test06_logout_handler(self):
        with dummy_app.test_request_context('/a_request'):
            auth = IIIFAuthGoogle(client_secret_file=csf)
            response = auth.logout_handler()
            self.assertEqual( response.status_code, 200 )
            self.assertEqual( response.headers['Content-type'], 'text/html' )
            html = response.get_data()
            self.assertTrue( re.search(r'<script>window.close\(\);</script>',html) )

    def test07_access_token_handler(self):
        with dummy_app.test_request_context('/a_request'):
            auth = IIIFAuthGoogle(client_secret_file=csf)
            response = auth.access_token_handler()
            self.assertEqual( response.status_code, 200 )
            self.assertEqual( response.headers['Content-type'], 'application/json' )
            j = json.loads(response.get_data())
            self.assertEqual( j['error_description'], "No login details received" )
            self.assertEqual( j['error'], "client_unauthorized" )
        # add callback but no account cookie
        with dummy_app.test_request_context('/a_request?callback=CB'):
            auth = IIIFAuthGoogle(client_secret_file=csf)
            response = auth.access_token_handler()
            self.assertEqual( response.status_code, 200 )
            self.assertEqual( response.headers['Content-type'], 'application/javascript' )
            # strip JavaScript wrapper and then check JSON
            js = response.get_data()
            self.assertTrue( re.match('CB\(.*\);',js) )
            j = json.loads(js.lstrip('CB(').rstrip(');'))
            self.assertEqual( j['error_description'], "No login details received" )
            self.assertEqual( j['error'], "client_unauthorized" )
        # add an account cookie
        h = Headers()
        h.add('Cookie', 'lol_account=ACCOUNT_TOKEN')
        with dummy_app.test_request_context('/a_request', headers=h):
            auth = IIIFAuthGoogle(client_secret_file=csf, cookie_prefix='lol_')
            response = auth.access_token_handler()
            self.assertEqual( response.status_code, 200 )
            self.assertEqual( response.headers['Content-type'], 'application/json' )
            j = json.loads(response.get_data())
            self.assertEqual( j['access_token'], "ACCOUNT_TOKEN" )
            self.assertEqual( j['token_type'], "Bearer" )
 

    def test07_home_handler(self):
        with dummy_app.test_request_context('/a_request'):
            auth = IIIFAuthGoogle(client_secret_file=csf)
            # Avoid actual calls to Google by mocking methods used by home_handler()
            auth.google_get_token = mock.Mock(return_value='ignored')
            auth.google_get_data = mock.Mock(return_value={'email':'e@mail','name':'a name'})
            response = auth.home_handler()
            self.assertEqual( response.status_code, 200 )
            self.assertEqual( response.headers['Content-type'], 'text/html' )
            html = response.get_data()
            self.assertTrue( re.search(r'<script>window.close\(\);</script>',html) )

    def test08_google_get_token(self):
        with dummy_app.test_request_context('/a_request'):
            with mock.patch('urllib2.urlopen', return_value=Readable('{"a":"b"}')):
                auth = IIIFAuthGoogle(client_secret_file=csf)
                config = Struct(host='a_host',port=None)
                j = auth.google_get_token(config,'prefix')
                self.assertEqual( j, {'a':'b'} )

    def test09_google_get_data(self):
        with dummy_app.test_request_context('/a_request'):
            with mock.patch('urllib2.urlopen', return_value=Readable('{"c":"d"}')):
                auth = IIIFAuthGoogle(client_secret_file=csf)
                config = Struct(host='a_host',port=None)
                j = auth.google_get_data(config,{'access_token':'TOKEN'})
                self.assertEqual( j, {'c':'d'} )