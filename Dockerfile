# FROM tiangolo/uwsgi-nginx:python3.9 as builder

# WORKDIR /app
# COPY Pipfile Pipfile.lock ./
# RUN pip install pipenv
# RUN pipenv install --dev --system

# COPY . .
# RUN pytest
FROM registry.access.redhat.com/ubi8/ubi

WORKDIR /app
COPY --chown=1000 Pipfile Pipfile.lock ./
RUN yum install -y python39 \
   R && yum clean all \
    && python3 -m pip install pipenv \
    && chown -R 1000 ./ \
    && pipenv install --system --deploy
COPY --chown=1000 . .
RUN pytest
USER 1000

EXPOSE 5000
#https://github.com/tiangolo/uwsgi-nginx-docker#readme        
CMD [ "waitress-serve", "--port=5000", "--expose-tracebacks", "--threads=8", "--call", "project.server.app:create_app" ]
