FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Flaw: No USER instruction, defaults to root
CMD ["flask", "run", "--host=0.0.0.0"]
