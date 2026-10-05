FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python generate_data.py

EXPOSE 8501
EXPOSE 8000

CMD ["sh", "-c", "python metrics_server.py & streamlit run app.py --server.address=0.0.0.0 --server.port=8501"]