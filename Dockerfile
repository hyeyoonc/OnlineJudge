FROM python:3.9-slim

ENV OJ_ENV production

ADD . /app
WORKDIR /app

# HEALTHCHECK --interval=5s --retries=3 CMD python3 /app/deploy/health_check.py

# RUN apk add --update --no-cache build-base nginx openssl curl unzip supervisor jpeg-dev zlib-dev postgresql-dev freetype-dev && \
#     pip install --no-cache-dir -r /app/deploy/requirements.txt && \
#     apk del build-base --purge
ENV OJ_ENV dev
RUN apt-get update && apt-get install -y \
    # dev essentials
    python python-dev python3 python3-dev python3-pip virtualenv libssl-dev libpq-dev git \
    build-essential libfontconfig1 libfontconfig1-dev \
    # web serving things (uwsgi is in pip requirements.txt)
    nginx supervisor redis-server celery\
    # network tools
    net-tools vim postgresql-client curl && \
    pip install --no-cache-dir -r /app/deploy/requirements.txt
RUN         cp -f deploy/nginx/nginx.conf     /etc/nginx/nginx.conf &&\
    cp -f deploy/supervisord.conf  /etc/supervisor/conf.d/
RUN         echo -e "\n" > /app/data/config/secret.key
# front 쪽
# RUN curl -L  $(curl -s  https://api.github.com/repos/QingdaoU/OnlineJudgeFE/releases/latest | grep /dist.zip | cut -d '"' -f 4) -o dist.zip && \
#     unzip dist.zip && \
#     rm dist.zip

EXPOSE 80
# CMD         ["supervisord", "-n"]
ENTRYPOINT /app/deploy/entrypoint.sh
