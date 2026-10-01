FROM frappe/bench:latest

USER root

COPY --chown=frappe:frappe docker/init.sh /usr/local/bin/lms-init.sh
COPY --chown=frappe:frappe docker/start.sh /usr/local/bin/lms-start.sh
COPY --chown=frappe:frappe docker/tcp_proxy.py /usr/local/bin/lms-tcp-proxy.py
RUN chmod 0755 /usr/local/bin/lms-init.sh /usr/local/bin/lms-start.sh /usr/local/bin/lms-tcp-proxy.py

WORKDIR /home/frappe

ENTRYPOINT ["/usr/local/bin/lms-init.sh"]
