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

# Extract selected region from the response
region_code=$(echo "$response" | jq -r '.["optimal-regions"][0]' | sed 's/.*://')
# searches for '-'' followed by '0-9' -> replaces with empty string
# region_code=$(echo "$selected_region" | cut -d ':' -f 2 | sed 's/-[0-9]$//')
echo "$region_code"

# Edit pod YAML file using yq
yq eval -i ".metadata.name = \"greengrader-${submissionID}\"" pod.yaml
yq eval -i ".spec.containers[0].name = \"autograder-pod-${assignmentID}\"" pod.yaml
yq eval -i ".spec.containers[0].image |= sub(\"gitlab-registry.nrp-nautilus.io/c3lab/greengrader/autograder/[^\:]*\"; \"gitlab-registry.nrp-nautilus.io/c3lab/greengrader/autograder/${assignmentID}\")" pod.yaml
yq eval -i ".spec.affinity.nodeAffinity.preferredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms[0].matchExpressions[0].values[0] = \"$region_code\"" pod.yaml

 # Edit YAML file using sed
# sed -i "s/name: greengrader-[^ ]*/name: greengrader-${submissionID}/" greentest.yaml
# sed -i "s/\(name: autograder-pod-\)[^ ]*/\1${assignmentID}/" greentest.yaml
# sed -i "s/\(gitlab-registry\.nrp-nautilus\.io\/c3lab\/greengrader\/autograder\/\)[^:]*\(:1\.0\)/\1${assignmentID}\2/" greentest.yaml
#sed -i "s/\(values:\n\s*-\s*\)[^ ]*/\1${region_code}/" greentest.yaml

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
node_data=$(kubectl describe pod "greengrader-$submissionId"  | grep -m1 "Node" | awk '{print $2}')
node=$(echo $node_data | cut -d'/' -f1)
node_ip=$(echo $node_data | cut -d'/' -f2)
node_lat=$(curl -s ipinfo.io/$node_ip | jq -r .loc | sed 's/^\([0-9]\+\.[0-9]\+\),\(-*[0-9]\+\.[0-9]\+\)$/\1/')
node_lon=$(curl -s ipinfo.io/$node_ip | jq -r .loc | sed 's/^\([0-9]\+\.[0-9]\+\),\(-*[0-9]\+\.[0-9]\+\)$/\2/')

# Delete pod
kubectl delete pod greengrader-${submissionID}

# Extract values from metadata
db_id=$(psql -d greengrader -c "SELECT id FROM submissions WHERE submission_id=$submissionID" | sed -n '3p' | bc)
visibility=$(jq .visibility ./gradescope_data/results/results.json | sed 's/\"//g')
tests=$(jq .tests ./gradescope_data/results/results.json)
leaderboard=$(jq .leaderboard ./gradescope_data/results/results.json)
score=$(jq .score ./gradescope_data/results/results.json)
execution_time=$((cte - cts))
total_time=$((tte - tts))
total_time_sec=$((total_time / 1000))

psql -d greengrader -c "INSERT INTO results (id, submission_id, server, visibility, tests, leaderboard, score, execution_time, total_time, execution_power, carbon_intensity, region, node, node_ip) VALUES ($db_id, $submissionID, 'c10-01', '$visibility', ARRAY$tests::json[], ARRAY$leaderboard::json[], $score, $execution_time, $total_time, 0.0, 0.0, '$region_code', '$node', '$node_ip'::inet);"

carbon_response=$(curl --header "Content-Type: application/json" \
          --request GET \
            --data '{"runtime":'$total_time_sec',"schedule":{"type":"onetime","start_time":"'${start_time}'","max_delay":0},"dataset":{"input_size_gb":0,"output_size_gb":0}, "candidate_locations": [{"id": "Nautilus:'$region_code'", "latitude": '$node_lat', "longitude": '$node_lon'}],"use_prediction": true,"carbon_data_source": "azure"}' \
              https://cas-carbon-api-dev.nrp-nautilus.io/carbon-aware-scheduler/)

echo $carbon_response
