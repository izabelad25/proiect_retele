FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=9000
ENV MONGO_URI=mongodb://mongo:27017

EXPOSE 9000

CMD ["python", "server.py"]
