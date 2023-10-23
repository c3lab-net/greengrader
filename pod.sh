#!/bin/sh
##############################################################################
# GreenGrader Pod Spawner
# Uses AssignmentID and SubmissionID to
# AssignmentID is the pod name uploaded on registry
# SubmissionID names the specific pod from gradescope 
#
# Authors: Malcolm McSwain, Joshua Santillan
##############################################################################

# Command Line Arguments
assignmentID="$1"
submissionID="$2"

start_time=$(date -Iseconds)

# API request to get best regions (Changes Affinity in Yaml for preffered regions) 
response=$(curl --header "Content-Type: application/json" \
	  --request GET \
	    --data '{"runtime":50,"schedule":{"type":"onetime","start_time":"'${start_time}'","max_delay":0},"dataset":{"input_size_gb":0,"output_size_gb":0},"candidate_providers": ["Nautilus"],"use_prediction": true,"carbon_data_source": "azure"}' \
	      https://cas-carbon-api-dev.nrp-nautilus.io/carbon-aware-scheduler/)

echo "$response"

weighted_scores=$(echo "$response" | jq -r '.["weighted-scores"]' ) 
#echo "$weighted_scores"

# use external python script to find the optimal untainted node (region + zone)
region_zone=$(python3 fetch_zone.py "$weighted_scores")
expected_region_code=$(echo "$region_zone" | cut -d '.' -f 1)
expected_zone_code=$(echo "$region_zone"| cut -d '.' -f 2 )

# region_string=$(echo "$response" | jq -r '.["optimal-regions"][0]')
# expected_region_code=$(echo "$region_string" | cut -d ':' -f 2 | cut -d '.' -f 1)
# expected_zone_code=$(echo "$region_string" | cut -d ':' -f 2 | cut -d '.' -f 2)
# expected_region_and_zone_code="$expected_region_code.$expected_zone_code"

echo "Expected region code - $expected_region_code"
echo "Expected zone code - $expected_zone_code"

# Edit pod YAML file using yq
yq eval -i ".metadata.name = \"greengrader-${submissionID}\"" pod.yaml
yq eval -i ".spec.containers[0].name = \"autograder-pod-${assignmentID}\"" pod.yaml
yq eval -i ".spec.containers[0].image |= sub(\"gitlab-registry.nrp-nautilus.io/c3lab/greengrader/autograder/[^\:]*\"; \"gitlab-registry.nrp-nautilus.io/c3lab/greengrader/autograder/${assignmentID}\")" pod.yaml
yq eval -i ".spec.affinity.nodeAffinity.preferredDuringSchedulingIgnoredDuringExecution[0].preference.matchExpressions[0].values[0] = \"$expected_region_code\"" pod.yaml
# add zone code
yq eval -i ".spec.affinity.nodeAffinity.preferredDuringSchedulingIgnoredDuringExecution[0].preference.matchExpressions[1].values[0] = \"$expected_zone_code\"" pod.yaml

# Record turnaround timestart
tts=$(date +"%s%3N")
echo "Turnaround TIMESTART (epoch ms): $tts"

# Upload submission
rclone copy ./gradescope_data/submission greengrader-app:submission
echo "contents in greengrader-app:"
rclone ls greengrader-app:
# Start job
kubectl apply -f pod.yaml

# Wait for job to complete and download results
target_pod="greengrader-$submissionID"
while :; do
  echo "Checking pod status..."
  pod_status="$(kubectl get pod "$target_pod" | grep "$target_pod" | awk '{print $3}')"
  echo "Pod status for $target_pod: $pod_status"
  [ "$pod_status" = "Completed" ] && break || sleep 5
done

# Record turnaround timeend
tte=$(date +"%s%3N")
echo "Turnaround TIMEEND (epoch ms): $tte"

# Extract turnaround timestart from logs
ts=$(kubectl logs greengrader-${submissionID} autograder-pod-${assignmentID} --timestamps | grep "TIMESTART" | awk -F'Z' '{print $1}' | printf "%sZ\n" "$(cat -)")
cts=$(date -u +"%s%3N" --date=$ts)
echo "Container TIMESTART (epoch ms): $cts"

# Extract turnaround timeend from logs
te=$(kubectl logs greengrader-${submissionID} autograder-pod-${assignmentID} --timestamps | grep "TIMEEND" | awk -F'Z' '{print $1}' | printf "%sZ\n" "$(cat -)")
cte=$(date -u +"%s%3N" --date=$te)
echo "Container TIMEEND (epoch ms): $cte"

# Copy results into S3 greengrader storage using rclone 
rclone copy greengrader-app:results ./gradescope_data/results
rclone lsf --format "ts" greengrader-app:results/

# Extract node
node_data=$(kubectl describe pod "greengrader-$submissionID"  | grep -m1 "Node" | awk '{print $2}')
node=$(echo $node_data | cut -d'/' -f1)

# node_ip=$(echo $node_data | cut -d'/' -f2)
# node_lat=$(curl -s ipinfo.io/$node_ip | jq -r .loc | sed 's/^\([0-9]\+\.[0-9]\+\),\(-*[0-9]\+\.[0-9]\+\)$/\1/')
# node_lon=$(curl -s ipinfo.io/$node_ip | jq -r .loc | sed 's/^\([0-9]\+\.[0-9]\+\),\(-*[0-9]\+\.[0-9]\+\)$/\2/')

# Delete pod
kubectl delete pod greengrader-${submissionID}

# Extract region and zone from actual node
actual_region_code=$(kubectl describe node $node | grep "topology.kubernetes.io/region" | awk -F= '{print $2}' | tr -d '[:space:]')
actual_zone_code=$(kubectl describe node $node | grep "topology.kubernetes.io/zone" | awk -F= '{print $2}' | tr -d '[:space:]')
actual_region_and_zone_code="$actual_region_code.$actual_zone_code"

# Extract values from metadata
db_id=$(psql -d greengrader -c "SELECT id FROM submissions WHERE submission_id=$submissionID" | sed -n '3p' | bc)
visibility=$(jq .visibility ./gradescope_data/results/results.json | sed 's/\"//g')
tests=$(jq .tests ./gradescope_data/results/results.json)
leaderboard=$(jq .leaderboard ./gradescope_data/results/results.json)
score=$(jq .score ./gradescope_data/results/results.json)
execution_time=$((cte - cts))
total_time=$((tte - tts))
total_time_sec=$((total_time / 1000))

# fetch metrics for the run
carbon_response=$(curl --header "Content-Type: application/json" \
          --request GET \
          --data "{\"runtime\":$total_time_sec,\"schedule\":{\"type\":\"onetime\",\"start_time\":\"${start_time}\",\"max_delay\":0},\"dataset\":{\"input_size_gb\":0,\"output_size_gb\":0}, \"candidate_locations\": [{\"id\": \"Nautilus:${actual_region_and_zone_code}\"}],\"use_prediction\": true,\"carbon_data_source\": \"azure\"}" \
          https://cas-carbon-api-dev.nrp-nautilus.io/carbon-aware-scheduler/)

echo $carbon_response

# Extract details about execution using jq
energy_usage=$(echo "$carbon_response" | jq -r --arg region "Nautilus:$actual_region_and_zone_code" '.["raw-scores"][$region]."energy-usage"')
carbon_emission_from_compute=$(echo "$carbon_response" | jq -r --arg region "Nautilus:$actual_region_and_zone_code" '.["raw-scores"][$region]."carbon-emission-from-compute"')
carbon_emission_from_migration=$(echo "$carbon_response" | jq -r --arg region "Nautilus:$actual_region_and_zone_code" '.["raw-scores"][$region]."carbon-emission-from-migration"')
carbon_emission=$(echo "$carbon_response" | jq -r --arg region "Nautilus:$actual_region_and_zone_code" '.["raw-scores"][$region]."carbon-emission"')

# Populate results table
psql -d greengrader \
     -v v_db_id="$db_id" \
     -v v_submission_id="$submissionID" \
     -v v_server="c10-01" \
     -v v_visibility="$visibility" \
     -v v_tests="$tests" \
     -v v_leaderboard="$leaderboard" \
     -v v_score="$score" \
     -v v_start_time="$start_time" \
     -v v_execution_time="$execution_time" \
     -v v_total_time="$total_time" \
     -v v_energy_usage="$energy_usage" \
     -v v_carbon_emission_from_compute="$carbon_emission_from_compute" \
     -v v_carbon_emission_from_migration="$carbon_emission_from_migration" \
     -v v_carbon_emission="$carbon_emission" \
     -v v_region_code="$actual_region_and_zone_code" \
     -v v_node="$node" \
     -v v_node_ip="$node_ip" \
     -v v_node_lat="$node_lat" \
     -v v_node_lon="$node_lon" \
     -a -f insert.sql
