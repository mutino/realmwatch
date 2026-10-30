FROM node:22-alpine AS syntaxcheck
WORKDIR /check
COPY web/app.js ./app.js
RUN node --check app.js

FROM python:3.13-alpine
WORKDIR /app
COPY server.py ./
COPY web ./web
COPY --from=syntaxcheck /check/app.js ./web/app.js
USER 65534:65534
ENV BIND_HOST=0.0.0.0
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
CMD ["python", "-u", "server.py"]
