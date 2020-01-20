import os
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import exifread
import pprint

supported_image_file_extensions = ['.jpg', '.jpeg']
exif_tag_date_taken = 'EXIF DateTimeOriginal'
exif_datetime_format = '%Y:%m:%d %H:%M:%S'
dir_output_base = 'output/{0}/{1}/{2}'

class Watcher:
    DIRECTORY_TO_WATCH = "test/"

    def __init__(self):
        self.observer = Observer()

    def run(self):
        event_handler = Handler()
        self.observer.schedule(event_handler, self.DIRECTORY_TO_WATCH)
        self.observer.start()
        try:
            while True:
                time.sleep(5)
        except:
            self.observer.stop()
            print("Error")

        self.observer.join()


class Handler(FileSystemEventHandler):

    @staticmethod
    def on_any_event(event):
        if event.is_directory:
            return None

        elif event.event_type == 'created':
            process_file(event.src_path)

        elif event.event_type == 'modified':
            process_file(event.src_path)


def process_file(path):
    print("File path - %s." % path)
    # Step 1: Extract the file name and extension from the path
    file_name, file_extension = os.path.splitext((path))
    file_name_full = file_name + file_extension

    # Step 2: Filter away files that are not images
    print(file_extension_is_image(file_extension))
    if not file_extension_is_image(file_extension):
        return None
    # Step 3: Extract EXIF date taken from the image
    year, month = get_photo_timestamp(path)
    print(year)
    print(month)
    # Step 4: Move the file to the correct destination directory (skipping if it already exists)
    photo_output_path = create_output_path(year, month, file_name_full)
    print(photo_output_path)

    # Step 5: Delete the source file


# Checks if a file is an image or not
def file_extension_is_image(file_extension):
    print(file_extension)
    return file_extension.lower() in supported_image_file_extensions


def get_photo_timestamp(path):
    file = open(path, 'rb')
    tags = exifread.process_file(file, details=False, stop_tag=exif_tag_date_taken)
    # pp = pprint.PrettyPrinter(indent=4)
    # pp.pprint(tags)
    exif_datetime = tags.get(exif_tag_date_taken)
    photo_date = datetime.strptime('%s' % exif_datetime, exif_datetime_format)
    # print(photo_date.year)
    print('Photo time: %s' % exif_datetime)
    # Return the year and month as a tuple. Values are not zero-padded at this stage
    return photo_date.year, photo_date.month


def create_output_path(year, month, file_name):
    return dir_output_base.format(year, month, file_name)

if __name__ == '__main__':
    w = Watcher()
    w.run()