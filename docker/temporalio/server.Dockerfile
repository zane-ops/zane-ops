FROM temporalio/auto-setup:1.24.2

USER root
RUN mkdir -p /etc/temporal/archival && chown -R temporal:temporal /etc/temporal/archival

USER temporal