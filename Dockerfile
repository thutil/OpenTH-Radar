FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    curl \
    cron \
    supervisor \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

COPY requirements-minimal.txt .
COPY requirements-web.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements-web.txt
RUN pip install --no-cache-dir -r requirements-minimal.txt

COPY . .

RUN sed -i 's/\r$//' main.sh && chmod +x main.sh
RUN mkdir -p /app/radar /app/out /app/logs
RUN echo "*/15 * * * * cd /app && ./main.sh >> /app/logs/cron.log 2>&1" | crontab -

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]