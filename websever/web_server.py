import logging
from flask import Flask, request, render_template, jsonify

class ControlServer:
    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        
        self.system_state = {
            "target_value": 0.0,
            "is_running": False
        }
        
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        self.app.add_url_rule('/', view_func=self.index, methods=['GET', 'POST'])
        self.app.add_url_rule('/api/status', view_func=self.get_status, methods=['GET'])

    def index(self):
        """
        Renders the web page. 
        If POST: updates the state based on buttons.
        If GET: shows current state.
        """
        if request.method == 'POST':
            try:
                input_val = request.form.get('float_input')
                if input_val:
                    self.system_state['target_value'] = float(input_val)
            except ValueError:
                pass 

            action = request.form.get('action')
            if action == 'start':
                self.system_state['is_running'] = True
            elif action == 'stop':
                self.system_state['is_running'] = False
                
        return render_template('index.html', state=self.system_state)

    def get_status(self):
        """
        JSON Endpoint for external scripts to access data.
        """
        return jsonify(self.system_state)

    def run(self):
        print(f"Starting Web Server on http://localhost:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=True)

if __name__ == '__main__':
    server = ControlServer()
    server.run()