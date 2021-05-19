FROM ubuntu:20.04
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends ca-certificates python3 python-is-python3 python3-pip

WORKDIR /app

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY dns-tls-proxy.py .

ENTRYPOINT ["python3", "dns-tls-proxy.py"]