# Photosort

## What is it?
Photosort sorts photos into a folder structure based on the date they were taken. It watches a folder for new photos, and automatically processes any photos that appear.

## Why is it?
I built photosort to make dealing with photos from my DSLR easier. I was spending too much time looking at date taken timestamps and manually copy-pasting photos into year / month folders. I realised there must be a way I could automate this with some semi-janky Python.

## How does it work?
Photosort looks at the date taken in photos' EXIF data, and sorts them by moving them from an input folder to an output folder struture based on the date.

## What folder structure does it use?
Photosort uses three folders:
+ The input folder. Photosort watches this, and will automatically process any image that appears in this folder.
+ The output folder. Photosort will place new photos in sub-folders inside this folder, in the form of output / YYYY / MM.
+ The quarantine folder. Photosort will place any photos that it thinks might be duplicates in here.

## What logic does it use?
```
For each new file in input:
    Check if the file is an photo. If not exit.
        Extract the date from the photo's EXIF tags.
        Generate the desired destination path based on the year and month in the date.
        Check if there's already a photo at this path. If there is:
            Hash the new photo and the existing photo. If the hashes are identical:
                The files are identical, so delete the new photo.
            If they are not:
                Move the new photo to the quarantine folder.
        If there is not:
            Move the new photo from the input folder to the desired destination.
```

## Will it delete my photos by accident?
No. Photosort only ever deletes photos from the input folder, and it only does this when it finds an identical (byte-for-byte the same) photo in the output folder. When photosort finds a photo that may or may not be a duplicate, it moves it to the quarantine folder.

## How do I install it?
Run photosort using `docker-compose`:
```
version: "2.2"

services:
  photosort:
    image: tomhomewood/photosort:latest
    container_name: photosort
    restart: unless-stopped
    environment:
      - DIRECTORY_INPUT=/path/to/input/directory           # Optional, defaults to /photos/input
      - DIRECTORY_OUTPUT=/path/to/output/directory         # Optional, defaults to /photos/output
      - DIRECTORY_QUARANTINE=/path/to/quarantine/directory # Optional, defaults to /photos/quarantine
    volumes:
      - /input/path/on/host:/photos/input
      - /output/path/on/host:/photos/output
      - /quarantine/path/on/host:/photos/quarantine
```
*Don't give me crap about using compose 2.2.*