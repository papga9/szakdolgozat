import logging
import os
from flask import Flask, request, render_template, jsonify


class ControlServer:
    def __init__(self, host="raspberrypi.local", port=5000):
        self.host = host
        self.port = port
        self.app = Flask(__name__)

        self.system_state = {
            "is_running": False,
            "is_homing": False,
            "current_pos_mm": None,
            "current_voltage": None,
            "best_pos_mm": None,
            "best_voltage": None,
            "focal_length": None,
            "desired_cmd": None
        }

        # Simple shared-secret to restrict write access to main.py
        self.api_key = os.environ.get("API_UPDATE_KEY", "dev-secret")

        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        self.app.add_url_rule('/', view_func=self.index, methods=['GET', 'POST'])
        self.app.add_url_rule('/api/status', view_func=self.get_status, methods=['GET'])
        self.app.add_url_rule('/api/start', view_func=self.start_scan, methods=['POST'])
        self.app.add_url_rule('/api/stop', view_func=self.stop_scan, methods=['POST'])
        self.app.add_url_rule('/api/update', view_func=self.update_status, methods=['POST'])

    def index(self):
        if request.method == 'POST':
            action = request.form.get('action')
            if action in ('start', 'stop', 'home'):
                self.system_state['desired_cmd'] = action

        return render_template('index.html', state=self.system_state)

    def get_status(self):
        return jsonify(self.system_state)

    def start_scan(self):
        self.system_state['desired_cmd'] = 'start'
        return jsonify({"ok": True, "desired_cmd": 'start'})

    def stop_scan(self):
        self.system_state['desired_cmd'] = 'stop'
        return jsonify({"ok": True, "desired_cmd": 'stop'})

    def start_home(self):
        self.system_state['desired_cmd'] = 'home'
        return jsonify({"ok": True, "desired_cmd": 'home'})

    def update_status(self):
        # Require API key to prevent browser or other clients from updating
        key = request.headers.get('X-API-Key')
        if key != self.api_key:
            return jsonify({"ok": False, "error": "unauthorized"}), 401

        data = request.get_json(silent=True) or {}
        allowed = {
            'is_running', 'is_homing', 'target_value',
            'current_pos_mm', 'current_voltage',
            'best_pos_mm', 'best_voltage', 'focal_length'
        }
        for k in allowed:
            if k in data:
                self.system_state[k] = data[k]

        # Allow algorithm to clear handled command
        if data.get('desired_cmd') is None and 'desired_cmd' in self.system_state:
            self.system_state['desired_cmd'] = None

        return jsonify({"ok": True, "state": self.system_state})

    def run(self):
        print(f"Starting Web Server on http://raspberrypi.local:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=True)


if __name__ == '__main__':
    server = ControlServer()
    server.run()
