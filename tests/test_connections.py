import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from catalog_check import model, runtime


class ProviderHandler(BaseHTTPRequestHandler):
    calls = []
    response_code = 200

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        type(self).calls.append((self.path, dict(self.headers), body))
        self.send_response(type(self).response_code)
        if type(self).response_code == 307:
            self.send_header('Location', f'http://127.0.0.1:{self.server.server_port}/redirect-target')
        self.end_headers()
        if type(self).response_code != 200:
            self.wfile.write(b'{"error":"test-secret-must-not-leak"}')
            return
        mapping = {field: None for field in model.FIELDS}
        mapping.update(sku='SKU', name='Name', regular_price='Price')
        answer = {'connected': True} if 'connection test' in body['messages'][0]['content'] else mapping
        self.wfile.write(json.dumps({'model': 'test-provider', 'choices': [{'message': {'content': json.dumps(answer)}}]}).encode())


class ApiConnectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), ProviderHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        ProviderHandler.calls = []
        ProviderHandler.response_code = 200
        self.config = {'mode': 'api', 'base_url': f'http://127.0.0.1:{self.server.server_port}/v1', 'model': 'test-chat', 'api_key': 'test-secret-must-not-leak', 'format': 'json'}

    def test_connection_uses_chat_endpoint_and_does_not_return_key(self):
        result = model.test_connection(self.config)
        path, headers, body = ProviderHandler.calls[0]
        self.assertEqual(path, '/v1/chat/completions')
        self.assertEqual(headers['Authorization'], 'Bearer test-secret-must-not-leak')
        self.assertEqual(body['model'], 'test-chat')
        self.assertEqual(body['response_format'], {'type': 'json_object'})
        self.assertNotIn('chat_template_kwargs', body)
        self.assertNotIn('seed', body)
        self.assertEqual(result['engine']['kind'], 'api_model')
        self.assertNotIn('test-secret-must-not-leak', json.dumps(result))

    def test_mapping_sends_only_bounded_samples(self):
        profile = {'headers': ['SKU', 'Name', 'Price'], 'column_samples': {'SKU': ['001'], 'Name': ['X' * 300, 'Two', 'Three', 'NEVER_SEND_FOURTH'], 'Price': ['10']}, 'full_csv': 'NEVER_SEND_CSV'}
        result = model.suggest_mapping(profile, self.config)
        payload = json.dumps(ProviderHandler.calls[0][2])
        self.assertNotIn('NEVER_SEND', payload)
        self.assertNotIn('X' * 101, payload)
        self.assertEqual(result['mapping']['sku'], 'SKU')

    def test_prompt_only_omits_optional_response_format(self):
        model.test_connection({**self.config, 'format': 'prompt'})
        self.assertNotIn('response_format', ProviderHandler.calls[0][2])

    def test_schema_mode_preserves_identifier_constraints(self):
        model.suggest_mapping({'headers': ['SKU', 'Name', 'Price']}, {**self.config, 'format': 'schema'})
        schema = ProviderHandler.calls[0][2]['response_format']['json_schema']['schema']
        self.assertNotIn('SKU', schema['properties']['barcode']['anyOf'][0]['enum'])

    def test_provider_error_body_is_not_exposed(self):
        ProviderHandler.response_code = 401
        with self.assertRaisesRegex(RuntimeError, 'key was rejected') as error:
            model.test_connection(self.config)
        self.assertNotIn(self.config['api_key'], str(error.exception))

    def test_redirect_is_not_followed_with_credentials(self):
        ProviderHandler.response_code = 307
        with self.assertRaisesRegex(RuntimeError, 'redirected'):
            model.test_connection(self.config)
        self.assertEqual(len(ProviderHandler.calls), 1)

    def test_remote_settings_require_https_and_key(self):
        for base in ['http://provider.example/v1', 'https://user:secret@provider.example/v1', 'https://provider.example/v1?key=secret', 'https://provider.example/v1#fragment']:
            with self.subTest(base=base), self.assertRaises(ValueError):
                model.connection_settings({**self.config, 'base_url': base})
        with self.assertRaises(ValueError):
            model.connection_settings({**self.config, 'base_url': 'https://provider.example/v1', 'api_key': ''})
        with self.assertRaises(ValueError):
            model.connection_settings({**self.config, 'api_key': 'bad\nheader'})
        cleaned = model.connection_settings({**self.config, 'base_url': 'https://provider.example/v1/chat/completions/'})
        self.assertEqual(cleaned['base_url'], 'https://provider.example/v1')


class LocalStartupTests(unittest.TestCase):
    def test_install_is_explicit_when_files_are_missing(self):
        with patch.object(runtime, 'snapshot', return_value={'supported': True}), patch.object(runtime, 'installed', return_value=False):
            with self.assertRaisesRegex(ValueError, 'Install'):
                runtime.launch(install=False)

    def test_existing_install_starts_without_downloading(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(runtime, 'RUNTIME', Path(directory)), patch.object(runtime, 'installed', return_value=True), patch.object(runtime.subprocess, 'run') as run, patch.object(runtime.model, 'status', return_value={'ready': True}):
                runtime._worker(cpu=True)
                self.assertEqual(run.call_count, 1)
                command = run.call_args.args[0]
                self.assertIn(str(runtime.ROOT / 'scripts' / 'start_model.ps1'), command)
                self.assertIn('-Cpu', command)
                self.assertFalse(runtime.snapshot()['busy'])
                self.assertEqual(runtime.snapshot()['phase'], 'ready')


if __name__ == '__main__':
    unittest.main()
