import argparse
import json
import sqlite3

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description="Run the binning query, write the results to a file.")
    parser.add_argument('--db', type=str, default='file_info.db', help='The filename of the SQLite database to read.')
    parser.add_argument('--output', type=str, default='binned_data.json', help='The filename of the JSON file to write.')
    parser.add_argument('--unit', type=str, default='minute', help='The size of the bins to create.')

    args = parser.parse_args()

    # Connect to SQLite database
    conn = sqlite3.connect(args.db)
    cursor = conn.cursor()

    if args.unit not in ['minute', 'hour', 'day']:
        exit('--unit must be one of "minute", "hour", or "day"')

    if args.unit == 'day':
        dateformatstring = '%Y-%m-%d 00:00:00'
    elif args.unit == 'hour':
        dateformatstring = '%Y-%m-%d %H:00:00'
    else:
        dateformatstring = '%Y-%m-%d %H:%M:00'

    # Gather the requested bin information
    cursor.execute(
        f"""select
            strftime('{dateformatstring}', datetime(atime, 'unixepoch')) as timebin,
            count(*),
            sum(size)
            from files
            group by timebin
            order by timebin asc
        """
    )
    rows = cursor.fetchall()
    with open(args.output, "w") as file:
        json.dump(rows, file, indent=4)

    # Close the connection
    conn.close()

if __name__ == "__main__":
    main()
