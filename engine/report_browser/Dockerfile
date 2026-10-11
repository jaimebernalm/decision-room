ARG BASE_IMAGE=python@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends chromium fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir /opt/report /home/renderer && chown 10001:10001 /home/renderer
COPY chrome.py worker.py inventory.py /opt/report/
ENV HOME=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "-B", "/opt/report/worker.py"]
