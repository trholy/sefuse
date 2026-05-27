FROM ollama/ollama:0.24.0

COPY init_models.sh /init_models.sh
RUN chmod +x /init_models.sh && \
    (id ollama 2>/dev/null || useradd --system --no-create-home ollama)

EXPOSE 11434

USER ollama

ENTRYPOINT ["/init_models.sh"]
