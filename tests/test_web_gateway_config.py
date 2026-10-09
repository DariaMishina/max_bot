from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WebGatewayConfigTests(unittest.TestCase):
    def test_gateway_is_loopback_only_and_routes_expected_prefixes(self):
        config = (ROOT / "deploy/nginx-tarot-api-gateway.conf").read_text()

        self.assertIn("listen 127.0.0.1:8084;", config)
        self.assertIn("location ^~ /api/webapp/", config)
        self.assertIn("proxy_pass http://127.0.0.1:8081;", config)
        self.assertIn("location ^~ /v1/", config)
        self.assertIn("location ^~ /static/", config)
        self.assertGreaterEqual(config.count("proxy_pass http://127.0.0.1:8083;"), 2)
        self.assertIn("location / {\n        return 404;", config)

    def test_xtunnel_targets_gateway_and_waits_for_nginx(self):
        service = (ROOT / "deploy/xtunnel-app.service").read_text()

        self.assertIn("After=network-online.target nginx.service", service)
        self.assertIn("xtunnel http 8084 --local 127.0.0.1:8084", service)
        self.assertNotIn("xtunnel http 8083", service)


if __name__ == "__main__":
    unittest.main()
