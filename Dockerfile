# Dockerfile para servicio Python
FROM python:3.12

WORKDIR /app

COPY requirements.txt requirements.txt
RUN  pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

# Exponer el puerto 5000
EXPOSE 5000
CMD ["python", "app.py"]