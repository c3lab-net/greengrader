##############################################################################
# GreenGrader Receiver
# Listens for autograder results and experimental data via MQTT and commits 
# them to postgres.
#
# Authors: Malcolm McSwain, Joshua Santillan
##############################################################################

from paho.mqtt import client as mqtt_client
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from models import Results, Workers
import logging
import subprocess
import random
import json
import time
import os

# Logging configuration
logging.basicConfig(level=logging.DEBUG,handlers=[logging.FileHandler('receiver.log', mode='a')],format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

# Create a database engine
with open('db_secret.txt') as f:
    secret = f.read()
engine = create_engine(secret[:-1])
conn = engine.connect()

# Create a session
Session = sessionmaker(bind=engine)
session = Session()

# MQTT credentials 
broker = 'localhost'
port = 1883
topic = 'results'
client_id = f'python-mqtt-{random.randint(0, 1000)}'
username = 'admin'
with open('mqtt_secret.txt') as f:
    password = f.read()[:-1]

# MQTT function to register new worker in database
def register_worker(client, info):
    worker_metadata = info.split(',')

    try:
        new_worker = Workers(
                ip=worker_metadata[0],
                name=worker_metadata[1],
                cpu_model_name=worker_metadata[2],
                cpu_clock_rate=float(worker_metadata[3]),
                cpu_sockets=int(worker_metadata[4]),
                cpu_cores=int(worker_metadata[5]),
                cache_size=int(worker_metadata[6]),
                memory_size=int(worker_metadata[7])
        );

        session.add(new_worker)
        session.commit()
        client.publish(topic, 'success')
    
    except:
        client.publish(topic, 'error: invalid worker metadata')


# MQTT callback to update database with results and experimental data
def update_results(payload):

    # Extract results from payload
    payload_lines = payload.partition('\n')
    # Check for file header
    results_exist = len(payload_lines) > 3
    # Grab file header metadata
    submission_id = payload_lines[1]
    gradescope_id = payload_lines[2]
    
    # Commit results to database if successfully retrieved
    if results_exist:
        # Create new results json object
        results = json.loads(' '.join(payload_lines[3:]))
        
        # Create new results orm object from json
        new_result = Results(
            id=submission_id,
            submission_id=gradescope_id,
            server='c10-01',
            visibility=results["visibility"] if results_exist else None,
            tests=[json.dumps(result) for result in results["tests"]] if results_exist else None,
            leaderboard=[json.dumps(result) for result in results["leaderboard"]] if results_exist else None,
            score=results["score"] if results_exist else None
        )

        # Add the new results to the session and commit the changes to the database
        session.add(new_result)
        session.commit()

# Establish MQTT connection
def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print('Connected!')
            logger.info('Connected to MQTT Broker!')
        else:
            logger.critical('Failed to connect, return code %d\n', rc)
    # Set connecting client ID
    client = mqtt_client.Client(client_id)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client

# Subscribe to MQTT topic
def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        print('Message received!')
        print(len(msg.payload.decode().partition('\n')))
        print(' '.join(msg.payload.decode().partition('\n')[3:]))

        payload_lines = msg.payload.decode().partition('\n')
        func = payload_lines[1]
        
        if func == 'register':
            register_worker(client, payload_lines[2])
        elif func == 'results':
            update_results(msg.payload.decode())

    client.subscribe(topic)
    client.on_message = on_message

def run():
    logger.info('Connecting to MQTT broker...')
    client = connect_mqtt()
    logger.info('Subscribing...')
    subscribe(client)
    client.loop_forever()

if __name__ == '__main__':
    run()
