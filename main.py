import os
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import exifread
import pprint
import shutil
from pathlib import Path
import hashlib

from hashutils import HashUtils

DIRECTORY_INPUT = os.getenv('DIRECTORY_INPUT', '/photos/input')
DIRECTORY_OUTPUT = os.getenv('DIRECTORY_OUTPUT', '/photos/output')
DIRECTORY_QUARANTINE = os.getenv('DIRECTORY_QUARANTINE', '/photos/quarantine')

supported_image_file_extensions = ['.jpg', '.jpeg']
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
            print("Exiting...")

        self.observer.join()


class Handler(FileSystemEventHandler):

    @staticmethod
    def on_any_event(event):
        if debug():
            print('Received event in input directory: ' + event.event_type)
        if event.is_directory:
            return None

        elif event.event_type == 'created':
            process_file(event.src_path)

        # elif event.event_type == 'modified':
            # process_file(event.src_path)


def debug():
    return False


def prcoess_existing_files():
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
    file_is_image =  file_extension_is_image(file_extension)
    if not file_is_image:
        if debug():
            print('File is not an image, skipping...')
        return None
    # Step 3: Extract EXIF date taken from the image
    year, month = get_image_timestamp(input_path)
    # Step 4: Move the file to the correct destination directory (skipping if it already exists)
    image_output_dir = create_output_dir(year, month)
    image_output_path = image_output_dir + file_name_full
    if debug():
        print('Output path for this image will be: ' + image_output_path)
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
            move_file(input, quarantine_path)
            print('An image named ' + file_name_full + ' already exists, but its contents are not identical. The image has been moved to ' + quarantine_path + ' for quarantine')
        return None
    # Ensure the output directory exists before attempting to move the file
    ensure_directory_exists(image_output_dir)
    # Move the file
    move_file(input_path, image_output_path)
    print('Image ' + file_name_full + ' moved to: ' + image_output_path)


def does_file_exist(path):
    return os.path.isfile(path)


def ensure_directory_exists(path):
    Path(path).mkdir(parents=True, exist_ok=True)


# Checks if a file is an image or not
def file_extension_is_image(file_extension):
    if debug():
        print('Checking file extension: ' + file_extension)
    return file_extension.lower() in supported_image_file_extensions


def move_file(src_path, destination_path):
    #shutil.move(input_path, quarantine_path)
    #os.rename(src_path, destination_path)
    move_command = "mv {0} {1}".format(src_path, destination_path)
    print("Move command: " + move_command)
    os.system(move_command)
    touch_command = "touch {0}".format(destination_path)
    print("Touch command: " + touch_command)
    os.system(touch_command)     # This is needed for Moments to detect the new file for some reason!


def get_image_timestamp(path):
    file = open(path, 'rb')
    tags = exifread.process_file(file, details=False, stop_tag=exif_tag_date_taken)
    # pp = pprint.PrettyPrinter(indent=4)
    # pp.pprint(tags)
    exif_datetime = tags.get(exif_tag_date_taken)
    image_date = datetime.strptime('%s' % exif_datetime, exif_datetime_format)
    # print(image_date.year)
    if debug():
        print('Image capture time: %s' % exif_datetime)
    # Return the year and month as a tuple. Values are not zero-padded at this stage
    return image_date.year, image_date.month


def pretty_print_exif(tags):
    pprint.PrettyPrinter(indent=4).pprint(tags)


def create_output_dir(year, month):
    return dir_output_base.format(year, month)


if __name__ == '__main__':
    # First, process any files in the input directory. This takes care of any files that may have been added whilst photowatch was not running
    prcoess_existing_files()
    w = Watcher()
    w.run()