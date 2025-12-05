import logging
from flask import Flask, request, render_template, jsonify

app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

system_state = {
    "target_value": 0.0,
    "is_running": False
}

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Renders the web page. 
    If POST: updates the global state based on buttons/inputs.
    If GET: shows current state.
    """
    global system_state
    
    if request.method == 'POST':
        try:
            input_val = request.form.get('float_input')
            system_state['target_value'] = float(input_val) if input_val else 0.0
        except ValueError:
            pass

        action = request.form.get('action')
        if action == 'start':
            system_state['is_running'] = True
        elif action == 'stop':
            system_state['is_running'] = False
            
    return render_template('index.html', state=system_state)

@app.route('/api/status', methods=['GET'])
def get_status():
    """
    JSON Endpoint for external scripts to access data.
    """
    return jsonify(system_state)

if __name__ == '__main__':
    print("Starting Web Server on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)