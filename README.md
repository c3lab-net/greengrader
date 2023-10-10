# greengrader

GreenGrader is a carbon-aware distributed autograding system. It consists of two independent services: an ingestion pipeline (for receiving and storing jobs as they are forked from Gradescope) and an execution pipeline. (for pulling jobs from the database and scheduling them to be executed on a cluster) Currently, jobs are pulled from Gradescope via MQTT. This is implemented with an extra set of lines in the `run_autograder` script:

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
cp -a /gradescope/. /gradescope_data/
cp -a /autograder/. /gradescope_data/
zip -r gradescope_data.zip gradescope_data
mosquitto_pub -h <ingestion host> -u <mosquitto username> -P <mosquitto password> -t submissions -f gradescope_data.zip
```

## Mosquitto MQTT
MQTT protocol for device to communicate by sending and receiving messages. Lightweight implementation of MQTT v3.

[Documentation](https://mosquitto.org/documentation/)

### Broker authenication
The password supplied by Gradescope run_autograder script


## Ingestion pipeline

[ingestion](./greengrader-ingest.py)

Daemon that listens to authenticated Mosquitto broker. When zipped submissions are sent over MQTT to the broker, the ingestion pipeline:
- writes it to the filesystem
- unzips it
- parses metadata included in the submission
- commits the raw payload and its metadata to the postgres database
- removes all generated intermediate files from the filesystem

## Execution pipeline

[exeuction](./greengrader-execute.py)

Consists of dispatcher, scheduler, and execution script.
- Dispatcher pulls jobs from database, sends to scheduler
- Scheduler deploys workload to worker node based on given scheduling policy
- Greengrader execute script is invoked, spawning an autograder Docker container
- Each worker node has a copy of execution script to call the payload to the worker node
- Scheduler invokes execution script via scp/ssh

### Dispatcher

Checks database for work on a timed interval.
- Sends available jobs to scheduler
- [Look up balancing authority](./api/routes/balancing_authority.py) based on GPS coordinates (via WattTime API)

### Scheduler
Dependencies: paramiko, scp

```
  usage: scheduler.py [-h] -f FILE [-c COMPUTE] [-t TIME] -w WORKERS [WORKERS ...] [-u USERNAME] [-p PASSWORD] -e EXECUTE [EXECUTE ...]

  Carbon-aware workload scheduler

  optional arguments:
    -h, --help            show this help message and exit
    -f FILE, --file FILE
    -c COMPUTE, --compute COMPUTE
    -t TIME, --time TIME
    -w WORKERS [WORKERS ...], --workers WORKERS [WORKERS ...]
    -u USERNAME, --username USERNAME
    -p PASSWORD, --password PASSWORD
    -e EXECUTE [EXECUTE ...], --execute EXECUTE [EXECUTE ...]
```
