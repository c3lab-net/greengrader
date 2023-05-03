##############################################################################
# GreenGrader Execution Pipeline
# Pulls submissions from database, executes autograder in Docker container,
# then commits results back to database
#
# Authors: Malcolm McSwain, Joshua Santillan
##############################################################################

from paho.mqtt import client as mqtt_client
import subprocess
import random
import base64
import json
import time
import os

# MQTT credentials
broker = '169.228.66.29' # c10-01
port = 1883
pub_topic = 'results'
sub_topic = 'jobs'
client_id = f'python-mqtt-{random.randint(0, 1000)}'
username = 'admin'
with open('mqtt_secret.txt') as f:
    password = f.read()[:-1]

# Takes in raw binary payload, unzips, and converts metadata into dict
def execute_submission(client, payload):
    
    print('Writing payload...')
    with open(os.getcwd()+'/gradescope_data.zip', 'wb') as f:
        f.write(payload)
    subprocess.run(['unzip',os.getcwd()+'/gradescope_data.zip'], check=True)    
    
    print('Reading metadata...')
    with open(os.getcwd()+'/gradescope_data/submission_metadata.json') as f:
        submission_metadata = json.load(f)

    submission_id = str(submission_metadata['id'])
    assignment_id = str(submission_metadata['assignment']['id'])

    # Build docker container & tag it with assignmentID, bind/mount file/directory -v creates endpoint as a directory
    # Run docker -rm deletes container after running.
    subprocess.run(['cp', os.getcwd()+'/Dockerfile', os.getcwd()+'/gradescope_data/Dockerfile'], check=True)
    subprocess.call(['chmod', '777', 'results/results.json'], cwd=os.getcwd()+'/gradescope_data')
    subprocess.call(['docker', 'build', '--no-cache', '-t', 'gradescope/autograder:'+assignment_id, '.'], cwd=os.getcwd()+'/gradescope_data')
    subprocess.run(['docker', 'run', '--rm', '-v', os.getcwd()+'/gradescope_data/results:/autograder/results', 'gradescope/autograder:'+assignment_id, '/autograder/run_autograder'], cwd=os.getcwd()+'/gradescope_data')
    print('Submission executed.')

    f_header = f'results\n{submission_id},{assignment_id}\n'
    f = open(os.getcwd()+'/gradescope_data/results/results.json')
    f_raw = bytes(f_header+f.read(), 'utf-8')
    client.publish(pub_topic, f_raw)
    print('Published to results!')
    return

# Attempts to connect to MQTT client given credentials, tries again on fail
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

# Subscribe to MQTT topic and listens for jobs to be scheduled
def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        print('Message received!')
        execute_submission(client, base64.b64decode(msg.payload))

    # subscribe and callback
    client.subscribe(sub_topic)
    client.on_message = on_message

def run():
    client = connect_mqtt()
    subscribe(client)
    client.loop_forever()

if __name__ == '__main__':
    run()

