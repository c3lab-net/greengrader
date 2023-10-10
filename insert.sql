PREPARE insert_plan (bigint, int, text, text, text, text, decimal, text, decimal, decimal, decimal, decimal, decimal, decimal, text, text, text, decimal, decimal) AS
  INSERT INTO results 
    (id, submission_id, server, visibility, tests, leaderboard, score, start_time, execution_time, total_time, energy_usage, carbon_emission_from_compute, carbon_emission_from_migration, carbon_emission, region, node, node_ip, node_lat, node_lon)
  VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19);

EXECUTE insert_plan(:v_db_id, :v_submission_id, :'v_server', :'v_visibility', :'v_tests', :'v_leaderboard', :v_score, :'v_start_time', :v_execution_time, :v_total_time, :v_energy_usage, :v_carbon_emission_from_compute, :v_carbon_emission_from_migration, :v_carbon_emission, :'v_region_code', :'v_node', :'v_node_ip', :v_node_lat, :v_node_lon);

DEALLOCATE insert_plan;
