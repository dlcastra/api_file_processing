# syntax=docker/dockerfile:1

# Comments are provided throughout this file to help you get started.
# If you need more help, visit the Dockerfile reference guide at
# https://docs.docker.com/go/dockerfile-reference/

# Want to help us make this template better? Share your feedback here: https://forms.gle/ybq9Krt8jtBL3iCk7

ARG PYTHON_VERSION=3.13.0
FROM python:${PYTHON_VERSION} AS base
ENV DOCKERIZED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN useradd -ms /bin/bash admin
WORKDIR /usr/src/service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Switch to a non-privileged user if necessary (optional)
USER admin

# Copy the source code into the container.
COPY . .

# Expose the port that the application listens on.
EXPOSE 8000
# Run the application.
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000"]
