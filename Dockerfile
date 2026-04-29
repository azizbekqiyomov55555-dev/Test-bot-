FROM python:3.10-slim

RUN apt-get update && apt-get install -y sqlite3 libsqlite3-0

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]
