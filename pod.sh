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

# API request to get best regions (Changes Affinity in Yaml for preffered regions) 
response=$(curl --header "Content-Type: application/json" \
	  --request GET \
	    --data '{"runtime":900,"schedule":{"type":"onetime","start_time":"2023-03-02T14:22:00-07:00","max_delay":0},"dataset":{"input_size_gb":0,"output_size_gb":0}}' \
	      http://yeti-09.sysnet.ucsd.edu/carbon-aware-scheduler/)

# Extract selected region from the response
selected_region=$(echo "$response" | jq -r '.["selected-region"]')
# searches for '-'' followed by '0-9' -> replaces with empty string
region_code=$(echo "$selected_region" | cut -d ':' -f 2 | sed 's/-[0-9]$//')
echo "$region_code"

# Edit pod YAML file using yq
yq eval -i ".metadata.name = \"greengrader-${submissionID}\"" pod.yaml
yq eval -i ".spec.containers[0].name = \"autograder-pod-${assignmentID}\"" pod.yaml
yq eval -i ".spec.containers[0].image |= sub(\"gitlab-registry.nrp-nautilus.io/c3lab/greengrader/autograder/[^\:]*\"; \"gitlab-registry.nrp-nautilus.io/c3lab/greengrader/autograder/${assignmentID}\")" pod.yaml
yq eval -i ".spec.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms[0].matchExpressions[0].values[0] = \"$region_code\"" pod.yaml

 # Edit YAML file using sed
# sed -i "s/name: greengrader-[^ ]*/name: greengrader-${submissionID}/" greentest.yaml
# sed -i "s/\(name: autograder-pod-\)[^ ]*/\1${assignmentID}/" greentest.yaml
# sed -i "s/\(gitlab-registry\.nrp-nautilus\.io\/c3lab\/greengrader\/autograder\/\)[^:]*\(:1\.0\)/\1${assignmentID}\2/" greentest.yaml
#sed -i "s/\(values:\n\s*-\s*\)[^ ]*/\1${region_code}/" greentest.yaml


# Upload submission
rclone copy ./gradescope_data/submission greengrader-app:submission
echo "contents in greengrader-app:"
rclone ls greengrader-app:
# Start job
kubectl apply -f pod.yaml

# Record turnaround timestart
tts=$(date +"%s%3N")
echo "Turnaround TIMESTART (epoch ms): $tts"

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

psql -d greengrader -c "INSERT INTO results (id, submission_id, server, visibility, tests, leaderboard, score, execution_time, total_time, execution_power, carbon_intensity, region) VALUES ($db_id, $submissionID, 'c10-01', '$visibility', ARRAY$tests::json[], ARRAY$leaderboard::json[], $score, $execution_time, $total_time, 0.0, 0.0, '$region_code');"
