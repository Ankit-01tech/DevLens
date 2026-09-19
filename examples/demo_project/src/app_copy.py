import os

# TODO: refactor this whole module, it's a mess
# FIXME: the api key below should not be hardcoded

API_KEY = "sk_live_51H8xyzTHISISFAKEDONOTUSE1234567890abcd"

def get_config():
    db_url = "postgresql://admin:SuperSecretPass1@db.internal.example.com:5432/prod"
    return {"db_url": db_url, "api_key": API_KEY}

class ConfigManager:
    def __init__(self):
        self.config = get_config()

    def reload(self):
        # XXX: this doesn't actually reload anything yet
        pass
