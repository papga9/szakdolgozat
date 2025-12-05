import requests
import time
import sys

SERVER_URL = "http://localhost:5000/api/status"

def monitor_server():
    print(f"Connecting to control server at {SERVER_URL}...")
    print("Press Ctrl+C to exit.\n")

    while True:
        try:
            response = requests.get(SERVER_URL)
            
            if response.status_code == 200:
                data = response.json()
                
                value = data.get('target_value')
                running = data.get('is_running')
                
                print(f"\rStatus: {'RUNNING' if running else 'STOPPED'} | Value: {value:.4f}", end="")
            else:
                print(f"\rError: Server returned status {response.status_code}", end="")
                
        except requests.exceptions.ConnectionError:
            print("\rConnection refused. Is server.py running?", end="")
        except Exception as e:
            print(f"\nAn error occurred: {e}")

        time.sleep(1)

if __name__ == "__main__":
    try:
        monitor_server()
    except KeyboardInterrupt:
        print("\nExiting monitor.")
        sys.exit(0)