# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies that might be needed by Python packages (if any)
# For example, if a library needed gcc or other build tools:
# RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Specify the command to run on container start for Cloud Functions
# (functions-framework will start a web server)
# The Functions Framework automatically looks for a function specified
# by the --entry-point flag during deployment (e.g., sj_morse_lead_generator in main.py)
# Default port for Functions Framework is 8080.
# This CMD is often handled by the Cloud Functions environment when deploying a container,
# but it's good practice to have it.
CMD exec functions-framework --target=sj_morse_lead_generator --port=8080
