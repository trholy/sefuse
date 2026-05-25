FROM ollama/ollama:latest

COPY init_models.sh /init_models.sh
RUN chmod +x /init_models.sh

EXPOSE 11434

ENTRYPOINT ["/bin/sh", "-c", "/bin/ollama serve & until ollama list >/dev/null 2>&1; do sleep 1; done && /init_models.sh && wait"]
