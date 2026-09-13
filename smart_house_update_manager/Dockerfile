FROM python:3.13.7-alpine3.22
ARG BUILD_VERSION=0.1.0
ARG BUILD_REPOSITORY_URL=https://github.com/aoliveira07/smart-house-update-manager
LABEL io.hass.name="Smart House Update Manager" \
      io.hass.description="Persistent maintenance and safe daily host reboot" \
      io.hass.type="addon" \
      io.hass.version="${BUILD_VERSION}" \
      io.hass.arch="amd64|aarch64" \
      org.opencontainers.image.source="${BUILD_REPOSITORY_URL}"
WORKDIR /opt/shum
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY templates ./templates
COPY static ./static
COPY run.sh /run.sh
RUN chmod 755 /run.sh
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8099
CMD ["/run.sh"]
