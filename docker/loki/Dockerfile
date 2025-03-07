FROM grafana/loki:3.4

COPY ./config.yaml /etc/loki/local-config.yaml

CMD ["-config.file=/etc/loki/local-config.yaml"]