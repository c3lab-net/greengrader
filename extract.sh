start=$(date -d "$(grep TIMESTART logfile.txt | cut -d' ' -f2-)" +%s.%N)
end=$(date -d "$(grep TIMEEND logfile.txt | cut -d' ' -f2-)" +%s.%N)
echo "Timestamp difference in milliseconds: $(echo "($end - $start) * 1000" | bc | cut -d'.' -f1)"
