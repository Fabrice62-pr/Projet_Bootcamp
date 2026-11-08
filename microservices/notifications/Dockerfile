# Microservice "Notifications" : image officielle Azure Functions (Python),
# pour faire tourner localement exactement le runtime d'Azure.
FROM mcr.microsoft.com/azure-functions/python:4-python3.12

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt /
RUN pip install -r /requirements.txt

COPY . /home/site/wwwroot
