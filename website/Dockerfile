FROM python:3-onbuild
COPY .
CMD [ "gunicorn", "--workers", "3", "--bind", "0.0.0.0:5000", "app:app" ]
