from paho.mqtt import client as mqtt_client
import random
import sys

# MQTT credentials
broker = '169.228.66.29' # c10-01
port = 1883
topic = 'results'
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

# Subscribe to MQTT topic
def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        if msg.payload.decode() == 'success':
            print('Successfully registered worker '+sys.argv[2]+' to GreenGrader database!')
        else:
            print(msg.payload.decode())
        sys.exit()

    client.subscribe(sub_topic)
    client.on_message = on_message

def run():
    client = connect_mqtt()
   # payload = f'register\n{sys.argv[i]+"," for i in range(1, len(sys.argv))}'
    payload = f'register\n{",".join([sys.argv[i] + "," for i in range(1, len(sys.argv))])}'
    client.publish(topic, payload)
    subscribe(client)
    client.loop_forever()

if __name__ == '__main__':
    run()
