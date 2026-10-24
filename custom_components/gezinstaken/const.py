"""Constanten voor de integratie Gezinstaken."""

from datetime import timedelta

DOMAIN = "gezinstaken"
CONF_URL = "url"
CONF_API_KEY = "api_key"
# Hoe vaak Home Assistant wijzigingen uit de app ophaalt.
SCAN_INTERVAL = timedelta(seconds=30)
