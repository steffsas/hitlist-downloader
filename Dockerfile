FROM python:3.13-alpine

# set time zone for cron jobs
RUN apk add --no-cache tzdata
ENV TZ=Europe/Berlin

# first layer should contain the dependencies
COPY ./requirements.txt /app/requirements.txt

# install dependencies
RUN pip install -r /app/requirements.txt

# copy the rest of the application
COPY . /app

# set the working directory
WORKDIR /app

# install dependencies
RUN pip install -r requirements.txt

# run the application
CMD ["python", "main.py"]