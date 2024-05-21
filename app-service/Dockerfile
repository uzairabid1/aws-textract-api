FROM nvidia/cuda:12.2.0-base-ubuntu22.04

RUN apt-get update -y --fix-missing && apt-get install -y python3-pip gunicorn3
RUN apt-get install python3-dotenv -y

COPY requirements.txt /opt/
COPY backend /opt/backend

RUN pip3 install -r /opt/requirements.txt
RUN pip3 install PyPDF2
WORKDIR /opt/backend

CMD ["gunicorn3", "-b", "0.0.0.0:5000", "wsgi:app", "--workers=5"]
