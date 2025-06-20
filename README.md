# Home Assistant Pyscript Scripts for Home 

For development use the `develop_hass` Jupyter notebook. 
If changing utils.py, update the notebok.


Running Victoria metrics


docker run -d \
  --name vmagent \
  --restart unless-stopped \
  -p 8429:8429 \
  --entrypoint /bin/sh \
  victoriametrics/vmagent \
  -c "echo '
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: \"homeassistant\"
    metrics_path: /api/prometheus
    scheme: http
    static_configs:
      - targets: [\"192.168.2.39:8123\"]
    authorization:
      type: Bearer
      credentials: ...
' > /tmp/config.yml && exec /vmagent-prod -promscrape.config=/tmp/config.yml -remoteWrite.url=http://192.168.2.39:8428/api/v1/write"

docker run -d \
  --name victoriametrics \
  --restart unless-stopped \
  -p 8428:8428 \
  victoriametrics/victoria-metrics


