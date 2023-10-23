import json 
import sys
from collections import defaultdict

# weighted scores from the output of CAS API
weighted_scores = json.loads(sys.argv[1])
# convert to list of tuples
weighted_scores = [(k.split(':')[1], v) for k, v in weighted_scores.items()]
# sort by weighted score
weighted_scores.sort(key=lambda x: x[1])

# read csv file containing untainted nodes
with open('untainted_nodes.csv', 'r') as f:
    # create a dictionary of zone-node mappings
    zone_node_mapping = defaultdict(list)
    for line in f:
        # split the line into a list
        line = line.strip().split(',')
        # add the zone and node to the dictionary
        zone_node_mapping[line[0]].append(line[1])

result=""
# iterate through the sorted list of tuples
for zone, score in weighted_scores:
    # if the node is in the dictionary
    if zone in zone_node_mapping:
        # store the most optimal zone
        result=zone
        break

print(result)

