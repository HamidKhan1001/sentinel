FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY sentinel ./sentinel
RUN pip install --no-cache-dir .
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/api/health')"
CMD ["sentinel", "serve", "--port", "8000"]
