# Build with an immutable local product sandbox image supplied by the operator.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY vendor.py /opt/engine/vendor.py
COPY LICENSE.opencode /usr/local/share/licenses/opencode/LICENSE
COPY vendor/ /opt/engine/vendor/
RUN python /opt/engine/vendor.py install --folder /opt/engine/vendor \
    && rm -rf /opt/engine/vendor \
    && mkdir -p /work /state /home/agent \
    && chown 10001:10001 /work /state /home/agent
ENV HOME=/home/agent \
    XDG_DATA_HOME=/state \
    OPENCODE_DISABLE_AUTOUPDATE=1 \
    OPENCODE_DISABLE_SHARE=1 \
    OPENCODE_DISABLE_CLAUDE_CODE=1 \
    OPENCODE_DISABLE_EXTERNAL_SKILLS=1 \
    OPENCODE_DISABLE_MODELS_FETCH=1 \
    OPENCODE_DISABLE_PROJECT_CONFIG=1 \
    OPENCODE_DISABLE_DEFAULT_PLUGINS=1 \
    MPLCONFIGDIR=/tmp/matplotlib
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/opencode"]
