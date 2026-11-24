# Rasa server: the model is trained while the image is built, so the container starts ready to serve.
FROM rasa/rasa:3.6.21-full
WORKDIR /app
COPY --chown=1001:0 careline_bot/ /app/
RUN rasa train --fixed-model-name careline --out /app/models
EXPOSE 5005
ENTRYPOINT ["rasa"]
CMD ["run", "--enable-api", "--port", "5005", "--model", "/app/models/careline.tar.gz", "--cors", "*"]
