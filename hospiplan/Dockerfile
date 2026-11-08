# Service Core (Django) : image de production.
# Python 3.13 : derniere version proposee par Azure App Service Linux,
# pour que l'environnement local et Azure se comportent pareil.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Les fichiers statiques sont figes dans l'image. La cle factice ne sert qu'a
# demarrer Django le temps de la commande ; la vraie arrive au lancement.
RUN DJANGO_SECRET_KEY=build-only-not-secret python manage.py collectstatic --noinput

# Utilisateur sans privileges.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn hospiplan.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120"]
