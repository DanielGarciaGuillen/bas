FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py control.py ./

EXPOSE 47808/udp

CMD ["python", "main.py"]
