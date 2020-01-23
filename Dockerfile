FROM python:3.7-slim-buster

ENV BUILD_BUILDNUMBER=$Build.BuildNumber
ENV BUILD_BUILDID=$Build.BuildId

# Install dependencies
RUN apt-get update && apt-get install -y build-essential git
RUN pip install poetry

WORKDIR /docker


# Copy source
COPY . /docker

# Remove the crap
RUN rm -rf ./.venv ./.idea ./__pycache__

# Start the party
CMD poetry run app