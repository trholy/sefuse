FROM postgres:16-alpine

COPY check_env.sh /check_env.sh
RUN chmod +x /check_env.sh

USER postgres

ENTRYPOINT ["/check_env.sh"]
CMD ["postgres"]
