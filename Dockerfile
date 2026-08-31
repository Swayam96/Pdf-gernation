FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_PATH=/usr/bin/chromium
ENV PDF_REPORT_MACHINE=1
ENV PDF_REPORT_NO_OPEN=1
ENV PDF_REPORT_OUTPUT_DIR=/app/generated_reports
# 2x instead of 4x scale — quarters per-slide render cost, needed on Render's low-CPU/RAM tiers
ENV PDF_REPORT_SCALE=2

WORKDIR /app
COPY . .
RUN mkdir -p /app/generated_reports

EXPOSE 8001
CMD ["python", "api.py"]
