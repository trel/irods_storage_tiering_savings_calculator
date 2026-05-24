import os
import sqlite3
import uuid
from pathlib import Path
import argparse
import time
import stat

def walk_directory(path, ignore_dirs):
    file_paths = []
    for root, dirs, files in os.walk(path):
        # Remove ignored directories from the list
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            # Store file paths as absolute paths
            file_paths.append(os.path.abspath(os.path.join(root, file)))
    return file_paths

def get_file_extension(file_path):
    return Path(file_path).suffix[1:]  # Get the file extension without the dot

def get_file_type(file_path):
    try:
        file_mode = os.lstat(file_path).st_mode
        # Using stat module to determine file type
        if stat.S_ISLNK(file_mode):
            return 'symlink'
        elif stat.S_ISREG(file_mode):
            return 'regular_file'
        elif stat.S_ISDIR(file_mode):
            return 'directory'
        elif stat.S_ISCHR(file_mode):
            return 'character_device'
        elif stat.S_ISBLK(file_mode):
            return 'block_device'
        elif stat.S_ISFIFO(file_mode):
            return 'fifo_pipe'
        elif stat.S_ISSOCK(file_mode):
            return 'socket'
        else:
            return 'unknown'
    except FileNotFoundError as e:
        return 'unknown'

def save_file_info(conn, file_path, verbosity):
    try:
        # Get file metadata
        file_type = get_file_type(file_path)
        metadata = os.stat(file_path)
        file_size = metadata.st_size
        modified_time = int(metadata.st_mtime)   # Last modified time
        atime = int(metadata.st_atime)           # Last access time
        ctime = int(metadata.st_ctime)           # Metadata change time (on unix)
        device_id = metadata.st_dev              # Device ID
        inode = metadata.st_ino                  # inode number
        extension = get_file_extension(file_path)

        # Check if the file already exists in the database by device_id + inode
        existing_file = conn.execute(
            "SELECT * FROM files WHERE device_id = ? AND inode = ?",
            (device_id, inode)
        ).fetchone()

        if existing_file:
            # Compare current metadata with the existing metadata
            if (
                existing_file[4] != file_size or
                existing_file[5] != modified_time or
                existing_file[6] != atime or
                existing_file[7] != ctime or
                existing_file[8] != extension or
                existing_file[9] != file_type
            ):
                # Update the existing record
                conn.execute(
                    """UPDATE files
                       SET size = ?, modified_time = ?, atime = ?, ctime = ?, extension = ?, type = ?
                       WHERE device_id = ? AND inode = ?""",
                    (file_size, modified_time, atime, ctime, extension, file_type, device_id, inode)
                )
                if verbosity > 1:
                    print(f"Updated file info for inode: {inode} on device: {device_id}")
                return 'updated'
        else:
            # Insert data into SQLite database
            conn.execute(
                """INSERT INTO files (device_id, inode, size, modified_time, atime, ctime, extension, type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (device_id, inode, file_size, modified_time, atime, ctime, extension, file_type)
            )
            if verbosity > 1:
                print(f"Inserted file info for inode: {inode} on device: {device_id}")
            return 'added'

    except Exception as e:
        if verbosity > 0:
            if file_type == 'symlink':
                print(f"Error dereferencing symlink: {e}")
            else:
                print(f"Error saving file info for {file_type}:{file_path}: {e}")
        return 'error'

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description="Walk a directory and save file metadata to a database.")
    parser.add_argument('path', type=str, help='The path of the directory to walk.')
    parser.add_argument('--db', type=str, default='file_info.db', help='The filename of the SQLite database to use.')
    parser.add_argument('--ignore-dirs', type=str, default='', help='Comma-separated list of directory names to ignore, e.g. ".git,node_modules"')
    parser.add_argument('--ignore-files', type=str, default='', help='Comma-separated list of filenames to ignore, e.g. "file1.txt,file2.jpg"')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress output. Will override --verbosity.')
    parser.add_argument('-v', '--verbosity', action='count', default=0, help='Increase verbosity level. Use -v for info, -vv for more verbose output.')

    args = parser.parse_args()

    # normal verbosity
    args.verbosity += 1

    # quiet should override verbosity
    if args.quiet:
        args.verbosity = 0

    # Split the ignore lists into sets
    ignore_dirs = set(args.ignore_dirs.split(',')) if args.ignore_dirs else set()
    ignore_files = set(args.ignore_files.split(',')) if args.ignore_files else set()

    # Connect to SQLite database
    conn = sqlite3.connect(args.db)

    # Create a table for storing file information
    conn.execute(
        """CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            device_id INTEGER NOT NULL,
            inode INTEGER NOT NULL,
            size INTEGER NOT NULL,
            modified_time INTEGER NOT NULL,
            atime INTEGER NOT NULL,
            ctime INTEGER NOT NULL,
            extension TEXT NOT NULL,
            type TEXT NOT NULL,
            UNIQUE(device_id, inode)
        )"""
    )

    # Specify the path you want to walk
    path = Path(args.path)

    # Collect all file paths, ignoring specified directories
    file_paths = walk_directory(path, ignore_dirs)

    # Initialize counters
    total_files_added = 0
    total_files_updated = 0
    total_files_ignored = 0
    total_files_errored = 0
    total_files_identical = 0
    total_files_found = 0

    # Record the start time
    start_time = time.time()

    # Process the file metadata
    for file_path in file_paths:
        total_files_found += 1

        # Ignore the file if it's in the ignore list
        if Path(file_path).name in ignore_files:
            total_files_ignored += 1
            if args.verbosity > 1:
                print(f"Ignoring file: {file_path}")
            continue

        result = save_file_info(conn, file_path, args.verbosity)
        if result == 'added':
            total_files_added += 1
        elif result == 'updated':
            total_files_updated += 1
        elif result == 'error':
            total_files_errored += 1
        else:
            total_files_identical += 1

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

    # Calculate elapsed time
    elapsed_time = time.time() - start_time

    # Print totals and elapsed time
    if args.verbosity > 0:
        justify_length = max(len(str(total_files_added)),
                             len(str(total_files_updated)),
                             len(str(total_files_ignored)),
                             len(str(total_files_errored)),
                             len(str(total_files_identical)),
                             len(str(total_files_found)),
                             )
        print(f"\nTotal Files:")
        print(f" Added:     {str(total_files_added).rjust(justify_length,' ')}")
        print(f" Updated:   {str(total_files_updated).rjust(justify_length,' ')}")
        print(f" Ignored:   {str(total_files_ignored).rjust(justify_length,' ')}")
        print(f" Errored:   {str(total_files_errored).rjust(justify_length,' ')}")
        print(f" Identical: {str(total_files_identical).rjust(justify_length,' ')}")
        print(f" Found:     {str(total_files_found).rjust(justify_length,' ')}")
        print(f"Elapsed time: {elapsed_time:.3f} seconds")

if __name__ == "__main__":
    main()
