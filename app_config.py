import json

with open("./app_config.json") as f:
    APP_CONFIG = json.loads(f.read())
