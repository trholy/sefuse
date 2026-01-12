FROM ollama/ollama:latest

COPY init_models.sh /init_models.sh
RUN chmod +x /init_models.sh

EXPOSE 11434

ENTRYPOINT ["/bin/sh", "-c", "/bin/ollama serve & sleep 5 && /init_models.sh && wait"]
