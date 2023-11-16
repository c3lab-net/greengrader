# greengrader

GreenGrader is a carbon-aware distributed autograding system. It consists of two independent services: an ingestion pipeline (for receiving and storing jobs as they are forked from Gradescope) and an execution pipeline. (for pulling jobs from the database and scheduling them to be executed on a cluster) Currently, jobs are pulled from Gradescope via MQTT. This can be implemented in any assignment by appending a few extra lines at the end of the `run_autograder` script, after autograding is complete and the results.json output is generated:

```
...
apt-get update && apt-get install -y zip mosquitto mosquitto-clients
cd /
mkdir gradescope_data
cd gradescope_data
hostname -I > hostname.txt
mkdir gradescope
mkdir autograder
cd ..
cp -a /gradescope/. /gradescope_data/gradescope/
cp -a /autograder/. /gradescope_data/autograder/
zip -r gradescope_data.zip gradescope_data
mosquitto_pub -h <ingestion host> -u <mosquitto username> -P <mosquitto password> -t submissions -f gradescope_data.zip
```

## Mosquitto MQTT
MQTT protocol for device to communicate by sending and receiving messages. Lightweight implementation of MQTT v3.

[Documentation](https://mosquitto.org/documentation/)

### Installation

```
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
```

### Starting the Broker

You can start the Mosquitto broker with:

```
sudo systemctl start mosquitto
```

By default, the broker will start on port 1883.

To enable Mosquitto to start on boot:

```
sudo systemctl enable mosquitto
```

### Broker authentication

Authentication can be configured in the mosquitto.conf file, typically located in /etc/mosquitto/ on Linux. After setting a username and password, these can be supplied to the broker via the `mosquitto_pub` command in the `run_autograder` script


## Ingestion Pipeline

Usage: 

```
nohup python3 ingest.py &
```

Daemon that listens to authenticated Mosquitto broker. When zipped submissions are sent over MQTT to the broker, the ingestion pipeline:
- writes it to the filesystem
- unzips it
- parses metadata included in the submission
- commits the raw payload and its metadata to the postgres database
- removes all generated intermediate files from the filesystem

## Dispatcher

Usage:

```
python3 dispatcher.py <submission id>
```

Can be run with or without submission id. If no submission id is supplied, pulls latest submission and passes it to relevant scheduler. Can also be used to load a submission to the filesystem for debugging.

## Kubernetes Execution Pipeline

Before invoking the pipeline, make sure your k8s environment is properly configured. [Setup instructions on NRP](https://ucsd-prp.gitlab.io/userdocs/start/quickstart/) Also, make sure the relevant `gradescope_data` and `pod.yaml` is loaded in the filesystem as `rclone` will upload it directly from the calling directory.

Usage: (can also be invoked from dispatcher)

```
./pod.sh <assignment id> <submission id>
```

Builds a kubernetes pod based on provided submission and podspec, waits for execution to complete, then records results to postgres database.

## Docker Execution Pipeline

On worker, make sure Mosquitto broker is running, then run:

```
python3 register.py <ip> <name> <cpu_model_name> <cpu_clock_rate> <cpu_sockets> <cpu_cores> <cache_size> <memory_size>
nohup python3 execute.py &
```

On scheduler, run:

```
nohup python3 receiver.py &
python3 scheduler.py
```

Consists of dispatcher, scheduler, and execution script.
- Dispatcher pulls jobs from database, sends to scheduler
- Scheduler deploys workload to worker node based on given scheduling policy
- Greengrader execute script is invoked, spawning an autograder Docker container
- Each worker node has a copy of execution script to call the payload to the worker node
- Receiver waits for results writeback and also listens for registration of new nodes

## Carbon-Aware Scheduling API

Pre-execution usage: (gets optimal region)

```
curl --header "Content-Type: application/json" \
          --request GET \
            --data '{"runtime":50,"schedule":{"type":"onetime","start_time":"'${start_time}'","max_delay":0},"dataset":{"input_size_gb":0,"output_size_gb":0},"candidate_providers": ["Nautilus"],"use_prediction": true,"carbon_data_source": "azure"}' \
              https://cas-carbon-api-dev.nrp-nautilus.io/carbon-aware-scheduler/
```

Post-execution usage: (gets carbon emitted for a given region)

```
curl --header "Content-Type: application/json" \
          --request GET \
          --data "{\"runtime\":$total_time_sec,\"schedule\":{\"type\":\"onetime\",\"start_time\":\"${start_time}\",\"max_delay\":0},\"dataset\":{\"input_size_gb\":0,\"output_size_gb\":0}, \"candidate_locations\": [{\"id\": \"Nautilus:${region_code}\"}],\"use_prediction\": true,\"carbon_data_source\": \"azure\"}" \
          https://cas-carbon-api-dev.nrp-nautilus.io/carbon-aware-scheduler/
```

Documentation: https://github.com/c3lab-net/k8s-carbon-aware-scheduler/
