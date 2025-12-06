import requests
import time
import sys

class ControlClient:
    def __init__(self, host="localhost", port=5000):
        self.base_url = f"http://{host}:{port}"
        self.api_url = f"{self.base_url}/api/status"

    def get_status(self):
        try:
            response = requests.get(self.api_url, timeout=2)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Server Error: {response.status_code}")
                return None
        except requests.exceptions.ConnectionError:
            print("Connection Error: Is the server running?")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None

    def set_target_value(self, value):
        try:
            payload = {'float_input': value}
            
            response = requests.post(self.base_url + "/", data=payload, timeout=2)
            
            if response.status_code == 200:
                return True
            else:
                print(f"Failed to send value. Server returned: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error sending value: {e}")
            return False

# for testing TODO delerte later
if __name__ == "__main__":
    client = ControlClient()
    print("Testing connection...")
    
    print("Attempting to set target value to 42.5...")
    if client.set_target_value(42.5):
        print("Value sent successfully!")
    
    print("\nMonitoring status (Press Ctrl+C to stop)...")
    while True:
        data = client.get_status()
        if data:
            state = "RUNNING" if data['is_running'] else "STOPPED"
            val = data['target_value']
            print(f"\r[Client Test] Status: {state} | Target: {val}   ", end="")
        time.sleep(1)