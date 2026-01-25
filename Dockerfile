FROM python

ENV PYTHONUNBUFFERED=true

COPY . /app

WORKDIR /app

RUN pip install -r requirements.txt

ENTRYPOINT ["python", "/app/swu.py"]