FROM ollama/ollama:0.24.0

COPY init_models.sh /init_models.sh
# UID pinned to 999 because setup.sh chowns the ./ollama/data bind mount to it on
# Linux hosts. Without --uid, useradd picks the next free system UID, which would
# silently shift if the base image ever adds another system user.
RUN chmod +x /init_models.sh && \
    (id ollama 2>/dev/null || useradd --system --no-create-home --uid 999 ollama)

EXPOSE 11434

USER ollama

ENTRYPOINT ["/init_models.sh"]
