FROM python:3.10-slim as build
RUN apt-get update
RUN apt-get install -y --no-install-recommends \
	build-essential gcc 

WORKDIR /usr/app
RUN python -m venv /usr/app/venv
ENV PATH="/usr/app/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.10-slim
RUN groupadd -g 999 python-group && \
    useradd -r -u 888 -g python-group python-user

RUN mkdir /usr/app && chown python-user:python-group /usr/app
WORKDIR /usr/app

COPY --chown=python-user:python-group --from=build /usr/app/venv ./venv
COPY --chown=python-user:python-group . .

USER 888

ENV PATH="/usr/app/venv/bin:$PATH"
CMD ["gunicorn", "-b", ":8080", "api:app"]