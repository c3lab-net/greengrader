##############################################################################
# GreenGrader Ingestion Pipeline
# Listens for Gradescope submissions via MQTT and commits them to postgres
#
# Authors: Malcolm McSwain, Joshua Santillan
##############################################################################

from paho.mqtt import client as mqtt_client
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func, cast, select
from models import Submission, Assignment
import logging
import subprocess
import random
import json
import time
import os   

# Logging credentials
logging.basicConfig(level=logging.DEBUG,handlers=[logging.FileHandler('ingest.log', mode='a')],format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

# Create a database engine
with open('db_secret.txt') as f:
    secret = f.read()
engine = create_engine(secret[:-1])
conn = engine.connect()

# Create a database session
Session = sessionmaker(bind=engine)
session = Session()

# MQTT credentials 
broker = 'localhost'
port = 1883
topic = 'submissions'
client_id = f'python-mqtt-{random.randint(0, 1000)}'
username = 'admin'
with open('mqtt_secret.txt') as f:
    password = f.read()[:-1]

# Builds assignment Docker container and pushes it to private registry
def build_container(assignment_id):
    print('Building container...')
    subprocess.run(['cp', os.getcwd()+'/Dockerfile', os.getcwd()+'/gradescope_data/Dockerfile'], check=True)
    subprocess.run(['docker', 'build', '--no-cache', '-t', 'gitlab-registry.nrp-nautilus.io/c3lab/greengrader/autograder/'+str(assignment_id)+':1.0', '.'], cwd=os.getcwd()+'/gradescope_data', check=True)
    print('Pushing to registry...')
    subprocess.run(['docker', 'push', 'gitlab-registry.nrp-nautilus.io/c3lab/greengrader/autograder/'+str(assignment_id)+':1.0'], cwd=os.getcwd()+'/gradescope_data', check=True)

    print('Adding assignment to database...')
    assignment = Assignment(id=assignment_id, version='1.0')
    session.add(assignment)
    session.commit()

# Takes in raw binary payload, unzips, and converts metadata into dict
def process_submission(payload):
    logger.info('Writing payload to filesystem...')
    with open(os.getcwd()+'/gradescope_data.zip', 'wb') as f:
        f.write(payload)
    logger.info('Unzipping contents...')
    subprocess.run(['unzip','gradescope_data.zip'], check=True)
    logger.info('Parsing JSON...')
    with open(os.getcwd()+'/gradescope_data/submission_metadata.json') as f:
        submission_metadata = json.load(f)
    with open(os.getcwd()+'/gradescope_data/hostname.txt') as f:
        submission_metadata['sender_ip'] = f.read()[:-2]
    submission_metadata['receiver_ip'] = '169.228.66.29' # c10-01
    logger.info('Submission data successfully captured.')

    # Check the database for existing assignment record
    assignment_id = submission_metadata['assignment']['id']
    query = select(Assignment).where(Assignment.id == assignment_id)
    output = session.execute(query)
    results = output.fetchall()

    # If assignment doesn't exist, build the container and upload it to nautilus registry
    if len(results) == 0:
        build_container(assignment_id)

    return submission_metadata

# Takes in metadata dict, commits relevant data to postgres
def commit_submission(metadata):
    # Create new submission object
    submission = Submission(
        submission_id=metadata["id"],
        status=0,
        payload=cast(func.pg_read_binary_file(f'{os.getcwd()}/gradescope_data.zip'), BYTEA),
        sender_ip=metadata["sender_ip"],
        receiver_ip=metadata["receiver_ip"],
        student_names=[user['name'] for user in metadata['users']],
        student_emails=[user['email'] for user in metadata['users']],
        student_ids=[user['id'] for user in metadata['users']],
        student_assignments=[{
            "release_date": user['assignment']['release_date'],
            "due_date": user['assignment']['due_date'],
            "late_due_date": user['assignment']['late_due_date']
        } for user in metadata['users']],
        created_at=metadata["created_at"],
        course_id=metadata["assignment"]["course_id"],
        assignment_id=metadata["assignment"]["id"],
        assignment_title=metadata["assignment"]["title"],
        assignment_release_date=metadata["assignment"]["release_date"],
        assignment_due_date=metadata["assignment"]["due_date"],
        assignment_late_due_date=metadata["assignment"]["late_due_date"],
        assignment_group_submission=metadata["assignment"]["group_submission"],
        assignment_group_size=metadata["assignment"]["group_size"],
        assignment_total_points=metadata["assignment"]["total_points"],
        assignment_outline=[{
            "id": outline['id'],
            "type": outline['type'],
            "title": outline['title'],
            "parent_id": outline['parent_id'],
            "weight": outline['weight']
        } for outline in metadata['assignment']['outline']],
        submission_method=metadata["submission_method"]
    )

    # Add submission to session and commit
    session.add(submission)
    session.commit()

# Establish MQTT connection
def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info('Connected to MQTT Broker!')
        else:
            logger.critical('Failed to connect, return code %d\n', rc)
    # Set connecting client ID
    client = mqtt_client.Client(client_id)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client

# Subscribe to MQTT topic, deletes processed files from local file-system when pushed into DB
def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        logger.info('Submission received.')
        metadata = process_submission(msg.payload)
        logger.info('Submission processed.')
        commit_submission(metadata)
        logger.info('Removing temporary files...')
        subprocess.run(['rm','-rf','gradescope_data','gradescope_data.zip'])
    client.subscribe(topic)
    client.on_message = on_message

def run():
    logger.info('Connecting to MQTT broker...')
    client = connect_mqtt()
    logger.info('Subscribing...')

    # subscribe and callback
    subscribe(client)
    client.loop_forever()

if __name__ == '__main__':
    run()
