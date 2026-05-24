#!/bin/bash -e

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <path_to_scan>"
  exit 1
fi

# get variables
PATH_TO_SCAN="$1"
FULLPATH=$(realpath "${PATH_TO_SCAN}")
BASENAME=$(basename "${FULLPATH}")
DBFILE="${BASENAME}.db"
JSONFILE="${BASENAME}.json"

# run scanner
echo "scanning [${FULLPATH}] ..."
python3 scanner.py --db "${DBFILE}" "${FULLPATH}"

# generate json
python3 generate_binned_data.py --db "${DBFILE}" --output "${JSONFILE}"
cp "${JSONFILE}" web.json

# start server (http://localhost:8000)
echo ""
echo "starting web server ..."
python3 -m http.server
