import unittest
import time
import requests
import multiprocessing
import logging
import datetime
import sys

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.DEBUG,
    format='%(asctime)s [%(threadName)s] [%(levelname)s] %(message)s'
)

import authenticated_test_service

import requests_auth.authentication as authentication
import requests_auth.oauth2_tokens as oauth2_tokens
import requests_auth.errors as errors


logger = logging.getLogger(__name__)


class JsonTokenFileCacheTest(unittest.TestCase):

    def setUp(self):
        global cache
        cache = oauth2_tokens.JsonTokenFileCache('test_tokens.cache')

    def tearDown(self):
        cache.clear()

    def test_add_tokens(self):
        expiry_in_1_hour = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        token1 = authenticated_test_service.create_token(expiry_in_1_hour)
        cache.add_token('key1', token1)

        expiry_in_2_hour = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        token2 = authenticated_test_service.create_token(expiry_in_2_hour)
        cache.add_token('key2', token2)

        # Assert that tokens can be retrieved properly even after other token were inserted
        self.assertEqual(cache.get_token('key1'), token1)
        self.assertEqual(cache.get_token('key2'), token2)

        # Assert that tokens are not removed from the cache on retrieval
        self.assertEqual(cache.get_token('key1'), token1)
        self.assertEqual(cache.get_token('key2'), token2)

    def test_save_load_tokens(self):
        expiry_in_1_hour = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        token1 = authenticated_test_service.create_token(expiry_in_1_hour)
        cache.add_token('key1', token1)

        expiry_in_2_hour = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        token2 = authenticated_test_service.create_token(expiry_in_2_hour)
        cache.add_token('key2', token2)

        same_cache = oauth2_tokens.JsonTokenFileCache('test_tokens.cache')
        self.assertEqual(same_cache.get_token('key1'), token1)
        self.assertEqual(same_cache.get_token('key2'), token2)

    def test_missing_token(self):
        with self.assertRaises(errors.AuthenticationFailed):
            cache.get_token('key1')

    def test_missing_token_function(self):
        expiry_in_1_hour = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        token = authenticated_test_service.create_token(expiry_in_1_hour)
        retrieved_token = cache.get_token('key1', lambda: ('key1', token))
        self.assertEqual(retrieved_token, token)


class MicrosoftOAuth2Test(unittest.TestCase):

    def test_corresponding_oauth2_instance(self):
        ms_auth = authentication.MicrosoftOAuth2('45239d18-c68c-4c47-8bdd-ce71ea1d50cd',
                                                 '54239d18-c68c-4c47-8bdd-ce71ea1d50cd',
                                                 '7362CAEA-9CA5-4B43-9BA3-34D7C303EBA7')
        self.assertEqual('https://login.microsoftonline.com/45239d18-c68c-4c47-8bdd-ce71ea1d50cd/oauth2/authorize?'
                         'client_id=54239d18-c68c-4c47-8bdd-ce71ea1d50cd'
                         '&response_type=id_token'
                         '&state=c141cf16f45343f37ca8053b6d0c67bad30a777b00221132d5a4514dd23082994e553a9f9fb45224ab9c2da3380047b32948fc2bf233efddc2fbd5801fc1d2d9'
                         '&redirect_uri=http%3A%2F%2Flocalhost%3A5000%2F'
                         '&response_mode=form_post'
                         '&nonce=%5B%277362CAEA-9CA5-4B43-9BA3-34D7C303EBA7%27%5D',
                         ms_auth.full_url)
        self.assertEqual("authentication.OAuth2("
                         "'https://login.microsoftonline.com/45239d18-c68c-4c47-8bdd-ce71ea1d50cd/oauth2/authorize', "
                         "redirect_uri_endpoint='', "
                         "redirect_uri_port=5000, "
                         "redirect_uri_port_availability_timeout=2.0, "
                         "token_reception_timeout=60, "
                         "token_reception_success_display_time=1, "
                         "token_reception_failure_display_time=5000, "
                         "client_id='54239d18-c68c-4c47-8bdd-ce71ea1d50cd', "
                         "response_type='id_token', "
                         "nonce='7362CAEA-9CA5-4B43-9BA3-34D7C303EBA7')",
                         str(ms_auth))


TEST_SERVICE_PORT = 5001  # TODO Should use a method to retrieve a free port instead
TEST_SERVICE_HOST = 'http://localhost:{0}'.format(TEST_SERVICE_PORT)
TIMEOUT = 5


def call(auth):
    return requests.get(TEST_SERVICE_HOST + '/get_headers', auth=auth, timeout=TIMEOUT)


def get_header(auth):
    response = requests.get(TEST_SERVICE_HOST + '/get_headers', auth=auth, timeout=TIMEOUT)
    response.raise_for_status()
    return dict(response.json())


def get_query_args(auth):
    response = requests.get(TEST_SERVICE_HOST + '/get_query_args', auth=auth, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def can_connect_to_server():
    try:
        resp = requests.get('http://localhost:{0}/status'.format(TEST_SERVICE_PORT), timeout=0.5)
        return resp.status_code == 200
    except:
        return False


def _wait_for_server_to_be_started():
    for attempt in range(3):
        if can_connect_to_server():
            logger.info('Test server is started')
            break
        logger.info('Test server still not started...')
    else:
        raise Exception('Test server was not able to start.')


class AuthenticationTest(unittest.TestCase):
    test_service_process = multiprocessing.Process(
        target=authenticated_test_service.start_server, args=(TEST_SERVICE_PORT,)
    )

    @classmethod
    def setUpClass(cls):
        cls.test_service_process.start()
        _wait_for_server_to_be_started()

    @classmethod
    def tearDownClass(cls):
        cls.test_service_process.terminate()
        cls.test_service_process.join(timeout=0.5)

    def setUp(self):
        authentication.OAuth2.token_cache.clear()

    def test_oauth2_url_is_mandatory(self):
        with self.assertRaises(Exception) as cm:
            authentication.OAuth2(None)
        self.assertEqual(str(cm.exception), 'Authorization URL is mandatory.')

    def test_oauth2_token_is_not_reused_if_a_url_parameter_is_changing(self):
        auth1 = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_token_as_custom_token?response_type=custom_token'
                                                          '&fake_param=1',
                                      token_reception_timeout=TIMEOUT)
        token_on_auth1 = get_header(auth1).get('Bearer')
        self.assertIsNotNone(token_on_auth1)

        # Ensure that the new generated token will be different than previous one
        time.sleep(1)

        logger.info('Requesting a custom token with a different parameter in URL.')

        auth2 = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_token_as_custom_token?response_type=custom_token'
                                                          '&fake_param=2',
                                      token_reception_timeout=TIMEOUT)
        token_on_auth2 = get_header(auth2).get('Bearer')
        self.assertIsNotNone(token_on_auth2)

        self.assertNotEqual(token_on_auth1, token_on_auth2)

    def test_oauth2_token_is_reused_if_only_nonce_differs(self):
        auth1 = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_token_as_custom_token?response_type=custom_token'
                                                          '&nonce=1',
                                      token_reception_timeout=TIMEOUT)
        token_on_auth1 = get_header(auth1).get('Bearer')
        self.assertIsNotNone(token_on_auth1)

        auth2 = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_token_as_custom_token?response_type=custom_token'
                                                          '&nonce=2',
                                      token_reception_timeout=TIMEOUT)
        token_on_auth2 = get_header(auth2).get('Bearer')
        self.assertIsNotNone(token_on_auth2)

        self.assertEqual(token_on_auth1, token_on_auth2)

    def test_oauth2_token_can_be_requested_on_a_custom_server_port(self):
        auth = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_token_as_token',
                                     # TODO Should use a method to retrieve a free port instead
                                     redirect_uri_port=5002,
                                     token_reception_timeout=TIMEOUT)
        self.assertIsNotNone(get_header(auth).get('Bearer'))

    def test_oauth2_token_is_sent_in_bearer(self):
        auth = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_token_as_token', token_reception_timeout=TIMEOUT)
        self.assertIsNotNone(get_header(auth).get('Bearer'))

    def test_oauth2_can_send_a_custom_response_type_and_expects_token_to_be_received_with_this_name(self):
        auth = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_token_as_custom_token',
                                     token_reception_timeout=TIMEOUT,
                                     response_type='custom_token')
        self.assertIsNotNone(get_header(auth).get('Bearer'))

    def test_oauth2_expects_token_to_be_stored_in_token_by_default(self):
        auth = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_token_as_token', token_reception_timeout=TIMEOUT)
        self.assertIsNotNone(get_header(auth).get('Bearer'))

    def test_oauth2_token_is_reused_if_not_expired(self):
        auth1 = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_token_as_token', token_reception_timeout=TIMEOUT)
        token1 = get_header(auth1).get('Bearer')
        self.assertIsNotNone(token1)

        oauth2 = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_token_as_token', token_reception_timeout=TIMEOUT)
        token2 = get_header(oauth2).get('Bearer')
        self.assertIsNotNone(token2)

        # As the token should not be expired, this call should use the same token
        self.assertEqual(token1, token2)

    def test_oauth2_failure_if_token_is_not_provided(self):
        with self.assertRaises(Exception) as cm:
            call(authentication.OAuth2(TEST_SERVICE_HOST + '/do_not_provide_token', token_reception_timeout=TIMEOUT))
        self.assertEqual('token not provided within {}.', str(cm.exception))

    def test_oauth2_failure_if_state_is_not_provided(self):
        with self.assertRaises(Exception) as cm:
            call(authentication.OAuth2(TEST_SERVICE_HOST + '/provide_token_as_token_but_without_providing_state',
                                       token_reception_timeout=TIMEOUT),)
        self.assertRegex(str(cm.exception), "state not provided within {'token': \['.*'\]}.")

    def test_oauth2_failure_if_token_is_not_received_within_the_timeout_interval(self):
        with self.assertRaises(Exception) as cm:
            call(authentication.OAuth2(TEST_SERVICE_HOST + '/do_not_redirect', token_reception_timeout=TIMEOUT))
        self.assertEqual('User authentication was not received within 5 seconds.', str(cm.exception))

    def test_oauth2_token_is_requested_again_if_expired(self):
        # This token will expires in 1 seconds
        auth1 = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_a_token_expiring_in_1_second',
                                      token_reception_timeout=TIMEOUT)
        token1 = get_header(auth1).get('Bearer')
        self.assertIsNotNone(token1)

        # Wait for 2 seconds to ensure that the token expiring in 1 seconds will be considered as expired
        time.sleep(2)

        # Token should now be expired, a new one should be requested
        auth2 = authentication.OAuth2(TEST_SERVICE_HOST + '/provide_a_token_expiring_in_1_second',
                                      token_reception_timeout=TIMEOUT)
        token2 = get_header(auth2).get('Bearer')
        self.assertIsNotNone(token2)

        self.assertNotEqual(token1, token2)

    def test_header_api_key_requires_an_api_key(self):
        with self.assertRaises(Exception) as cm:
            authentication.HeaderApiKey(None)
        self.assertEqual('API Key is mandatory.', str(cm.exception))

    def test_query_api_key_requires_an_api_key(self):
        with self.assertRaises(Exception) as cm:
            authentication.QueryApiKey(None)
        self.assertEqual('API Key is mandatory.', str(cm.exception))

    def test_header_api_key_is_sent_in_X_Api_Key_by_default(self):
        auth = authentication.HeaderApiKey('my_provided_api_key')
        self.assertEqual(get_header(auth).get('X-Api-Key'), 'my_provided_api_key')

    def test_query_api_key_is_sent_in_api_key_by_default(self):
        auth = authentication.QueryApiKey('my_provided_api_key')
        self.assertEqual(get_query_args(auth).get('api_key'), 'my_provided_api_key')

    def test_header_api_key_can_be_sent_in_a_custom_field_name(self):
        auth = authentication.HeaderApiKey('my_provided_api_key', 'X-API-HEADER-KEY')
        self.assertEqual(get_header(auth).get('X-Api-Header-Key'), 'my_provided_api_key')

    def test_query_api_key_can_be_sent_in_a_custom_field_name(self):
        auth = authentication.QueryApiKey('my_provided_api_key', 'X-API-QUERY-KEY')
        self.assertEqual(get_query_args(auth).get('X-API-QUERY-KEY'), 'my_provided_api_key')

    def test_basic_authentication_send_authorization_header(self):
        auth = authentication.Basic('test_user', 'test_pwd')
        self.assertEqual(get_header(auth).get('Authorization'), 'Basic dGVzdF91c2VyOnRlc3RfcHdk')

    def test_basic_and_api_key_authentication_can_be_combined(self):
        basic_auth = authentication.Basic('test_user', 'test_pwd')
        api_key_auth = authentication.HeaderApiKey('my_provided_api_key')
        header = get_header(authentication.Auths([basic_auth, api_key_auth]))
        self.assertEqual(header.get('Authorization'), 'Basic dGVzdF91c2VyOnRlc3RfcHdk')
        self.assertEqual(header.get('X-Api-Key'), 'my_provided_api_key')


if __name__ == '__main__':
    unittest.main(buffer=False)
