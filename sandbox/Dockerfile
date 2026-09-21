ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib HOME=/tmp
COPY requirements.lock /opt/requirements.lock
RUN python -m pip install --no-cache-dir --only-binary=:all: -r /opt/requirements.lock \
    && python -m pip check \
    && python -c "import importlib.metadata as m,json,platform; print(json.dumps({'python':platform.python_version(),'packages':{d.metadata['Name']:d.version for d in m.distributions()}},sort_keys=True))" > /opt/environment.json \
    && mkdir /inputs /output \
    && chmod 755 /inputs /output
COPY worker.py run_user.py dr_runtime.py /opt/
USER 10001:10001
WORKDIR /output
ENTRYPOINT ["python", "-I", "-B", "-u", "/opt/worker.py"]
