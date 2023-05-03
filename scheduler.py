##############################################################################
# Carbon-aware Workload Scheduler
# Generalized utility for scheduling workloads on remote machines. Given a set
# of scheduling policy parameters, workers, credentials, and a specification 
# of work-to-be-done, remotely executes the given workload on a specific node
#
# Authors: Malcolm McSwain, Joshua Santillan
##############################################################################

from paho.mqtt import client as mqtt_client
import requests
import argparse
import random
import base64
import json
import os

# Scheduler API params
url = "http://yeti-09.sysnet.ucsd.edu/carbon-aware-scheduler/"

headers = {
    "Content-Type": "application/json"
}

data = {
    "runtime": 900,
    "schedule": {
        "type": "onetime",
        "start_time": "2023-03-02T14:22:00-07:00",
        "max_delay": 0
    },
    "dataset": {
        "input_size_gb": 0,
        "output_size_gb": 0
    }
}

# Parse command line arguments
parser = argparse.ArgumentParser(description='Carbon-aware workload scheduler')
parser.add_argument('-f', '--file')
parser.add_argument('-c', '--compute')
parser.add_argument('-t', '--time')
parser.add_argument('-w', '--workers', nargs='+')
args = parser.parse_args()

# MQTT credentials
broker = '169.228.66.29' #c10-01
port = 1883
topic = 'jobs'
client_id = f'python-mqtt-{random.randint(0, 1000)}'
username = 'admin'
with open('mqtt_secret.txt') as f:
    password = f.read()[:-1]

def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)
    # Set Connecting Client ID
    client = mqtt_client.Client(client_id)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client

def run():
    # Scheduling policy (currently selects worker from cluster at random)
    # node = random.randint(0,len(args.workers)-1)
    # worker = args.workers[node]

    response = requests.post(url, headers=headers, data=json.dumps(data))

    #Carbon Aware API Request, returns carbon intensity data and the preferred region 
    if response.status_code == 200:
        json_response = json.loads(response.content.decode('utf-8'))
        selected_region = json_response['selected-region']
        print(selected_region)
    else:
        print('Error: ', response.status_code)

    client = connect_mqtt()
    f = open(os.getcwd() + '/' + args.file, 'rb')
    f_encode = base64.b64encode(f.read()).decode('utf-8')
    client.publish(topic, f_encode)

if __name__ == '__main__':
    run()
