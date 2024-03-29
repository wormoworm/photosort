import os
import time
from datetime import datetime, date
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import exifread
import pprint
import shutil
from pathlib import Path
import hashlib
from abc import ABC, abstractmethod
from subprocess import Popen, PIPE, run

from hashutils import HashUtils

DIRECTORY_INPUT = os.getenv('PHOTOSORT_DIRECTORY_INPUT', '/photos/input')
DIRECTORY_OUTPUT = os.getenv('PHOTOSORT_DIRECTORY_OUTPUT', '/photos/output')
DIRECTORY_QUARANTINE = os.getenv('PHOTOSORT_DIRECTORY_QUARANTINE', '/photos/quarantine')
MONITOR_CHANGES = os.getenv('PHOTOSORT_MONITOR_CHANGES', 'False').lower() in ['true', '1']
DRY_RUN = os.getenv('PHOTOSORT_DRY_RUN', 'False').lower() in ['true', '1']
DEBUG = os.getenv('PHOTOSORT_DEBUG', 'False').lower() in ['true', '1']

supported_image_file_extensions = ['.jpg', '.jpeg', '.mov', '.mp4']
exif_tag_date_taken = 'EXIF DateTimeOriginal'
exif_datetime_format = '%Y:%m:%d %H:%M:%S'
dir_output_base = DIRECTORY_OUTPUT + '/{0}/{1:02}/'

class Watcher:
    def __init__(self):
        self.observer = Observer()

    def run(self):
        event_handler = Handler()
        self.observer.schedule(event_handler, DIRECTORY_INPUT)
        self.observer.start()
        print('Watching ' + DIRECTORY_INPUT + ' for incoming images...')
        try:
            while True:
                time.sleep(5)
        except:
            self.observer.stop()
            print("Stopping watching...")

        self.observer.join()


class Handler(FileSystemEventHandler):

    @staticmethod
    def on_any_event(event):
        if debug():
            print('Received event in input directory: ' + event.event_type)
        if event.is_directory:
            return None

        #elif event.event_type == 'created':
        #    process_file(event.src_path)

        elif event.event_type == 'modified':
            time.sleep(1)   # This can help avoid processing files that are not yet fully written to disk.
            process_file(event.src_path)

class FileDateReader(ABC):

    @abstractmethod
    def get_file_date(self, file: str) -> date:
        """
        Return a date object representing when the file was created.
        """

class ExifreadDateReader(FileDateReader):

    def get_file_date(self, path: str):
        file = open(path, 'rb')
        tags = exifread.process_file(file, details=False, stop_tag=exif_tag_date_taken)
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(tags)
        exif_datetime = tags.get(exif_tag_date_taken)
        if exif_datetime == None:
            return -1
        try:
            file_date = datetime.strptime('%s' % exif_datetime, exif_datetime_format)
            # print(file_date.year)
            if debug():
                print('Image capture time: %s' % exif_datetime)
            # Return the date
            return file_date
        except ValueError as e:
             print('Error parsing file date: %s' % e)
             return -1

class ExiftoolDateReader(FileDateReader):

    def get_file_date(self, path: str):
        exiftool_process = Popen("exiftool -s -s -s -DateTimeOriginal {0}".format(path), shell=True, stdout=PIPE, stderr=PIPE)
        exiftool_process_out, exiftool_process_err = exiftool_process.communicate()
        exiftool_process_out_string = exiftool_process_out.decode("utf-8")
        exiftool_process_err_string = exiftool_process_err.decode("utf-8")
        return_code = exiftool_process.returncode
        if debug():
            print('Raw (but stripped) ExifTool output: {0}'.format(exiftool_process_out_string.strip()))

        if return_code != 0:
            if debug():
                print('Could not read file date')
                return -1

        exif_datetime = exiftool_process_out_string.strip()
        if debug():
            print('Exif datetime: {0}'.format(exif_datetime))
        try:
            file_date = datetime.strptime('%s' % exif_datetime, exif_datetime_format)
            if debug():
                print('File date: %s' % exif_datetime)
            # Return the date
            return file_date
        except ValueError as e:
             print('Error parsing file date: %s' % e)
             return -1


def debug():
    return DEBUG


def dry_run():
    return DRY_RUN


def process_existing_files():
    print('Scanning for existing files in ' + DIRECTORY_INPUT)
    for file in os.listdir(DIRECTORY_INPUT):
        process_file(DIRECTORY_INPUT + '/' + file)


def process_file(input_path):
    # Check the file still exists. The file watcher seems to deliver multiple events per file change, and they seem to all arrive at the same time. So after we have moved the file during the first call to this function, the file will no longer exist.
    if not does_file_exist(input_path):
        return None
    if debug():
        print("File path: " + input_path)
    # Step 1: Extract the file name and extension from the path
    path = Path(input_path)
    file_name = path.stem
    file_extension = path.suffix
    file_name_full = file_name + file_extension
    if debug():
        print('File: ' + file_name_full)
    # Step 2: Filter away files that are not images
    file_is_supported =  file_extension_is_supported(file_extension)
    if not file_is_supported:
        if debug():
            print('File is not supported, skipping...')
        return None
    # Step 3: Extract EXIF date taken from the image
    file_date = get_file_date(input_path)
    if file_date == -1:
        if debug():
            print("File date could not be read, skipping event...")
        return None
    # Step 4: Move the file to the correct destination directory (skipping if it already exists)
    image_output_dir = create_output_dir(file_date.year, file_date.month)
    image_output_path = image_output_dir + file_name_full
    if debug():
        print('Output path for this file will be: ' + image_output_path)
    file_exists = does_file_exist(image_output_path)
    if file_exists:
        # Now we will do an extra check to see if we are really dealing with the same file, or whether it's just a file name clash
        input_file_hash = HashUtils.get_file_hash(input_path)
        existing_file_hash = HashUtils.get_file_hash(image_output_path)
        if input_file_hash == existing_file_hash:
            # The two files are identical, so we can be 100% certain that we can discard the input file
            os.remove(input_path)
            print('An identical image already exists for ' + file_name_full + ', skipping and removing input image...')
        else:
            # The two files are not identical, so we will move the input file to a 'quarantine' directory, where the user can resolve the conflict manually
            quarantine_path = DIRECTORY_QUARANTINE + '/' + file_name_full
            ensure_directory_exists(DIRECTORY_QUARANTINE)
            move_file(input_path, quarantine_path)
            print('An image named ' + file_name_full + ' already exists, but its contents are not identical. The image has been moved to ' + quarantine_path + ' for quarantine')
        return None
    # Ensure the output directory exists before attempting to move the file
    ensure_directory_exists(image_output_dir)
    # Move the file
    if move_file(input_path, image_output_path):
        print('Image ' + file_name_full + ' moved to: ' + image_output_path)


def does_file_exist(path):
    return os.path.isfile(path)


def ensure_directory_exists(path) -> bool:
    if not dry_run():
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    else:
        if debug():
            print("Skipped creation of {0} due to dry run being set.".format(path))
        return False


# Checks if a file is supported or not
def file_extension_is_supported(file_extension) -> bool:
    if debug():
        print('Checking file extension: ' + file_extension)
    return file_extension.lower() in supported_image_file_extensions

def get_date_reader_for_file(path: str) -> FileDateReader:
    return ExiftoolDateReader()

def move_file(src_path, destination_path) -> bool:
    if not dry_run():
        move_command = "mv {0} {1}".format(src_path, destination_path)
        if debug():
            print("Move command: " + move_command)
        os.system(move_command)
        return True
    else:
        if debug():
            print("Skipped moving {0} to {1} due to dry run being set.".format(src_path, destination_path))
        return False


def get_file_date(path):    
    file_date = get_date_reader_for_file(path).get_file_date(path)
    return file_date


def pretty_print_exif(tags):
    pprint.PrettyPrinter(indent=4).pprint(tags)


def create_output_dir(year, month):
    return dir_output_base.format(year, month)


if __name__ == '__main__':
    # First, process any files in the input directory. This takes care of any files that may have been added whilst photowatch was not running
    process_existing_files()
    # Only monitor changes in the input directory if specified.
    if MONITOR_CHANGES:
        w = Watcher()
        w.run()
