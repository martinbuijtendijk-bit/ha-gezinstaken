# Gezinstaken voor Home Assistant

Integratie voor Home Assistant die de gedeelde takenlijsten van de webapp **Gezinstaken** als `todo`-entiteiten toont. Je ziet ze in de kaart *Takenlijst*, gebruikt ze met Assist ("zet melk op de boodschappenlijst") en in automatiseringen.

De webapp zelf staat niet in deze repo. Deze repo bevat alleen de koppeling, zonder gegevens of geheimen.

## Installeren (HACS)

1. HACS → ⋮ → **Custom repositories** → URL `https://github.com/martinbuijtendijk-bit/ha-gezinstaken`, type **Integration**.
2. Zoek **Gezinstaken** → **Download**, en herstart Home Assistant.
3. Maak in de webapp een sleutel aan: Instellingen → Koppelingen → *Sleutel maken*.
4. Home Assistant: Instellingen → Apparaten & diensten → **Integratie toevoegen** → *Gezinstaken*. Vul het adres van de app en de sleutel in.

## Wat werkt

- Elke **gedeelde** lijst wordt een entiteit, bijvoorbeeld `todo.gezinstaken_boodschappen`. Privélijsten blijven buiten Home Assistant.
- Taken toevoegen, wijzigen, afvinken, verwijderen en verplaatsen, met datum (zonder tijd) en omschrijving.
- Home Assistant haalt elke 30 seconden wijzigingen op, en direct na een wijziging vanuit Home Assistant. Nieuwe lijsten verschijnen vanzelf.
- Een ingetrokken sleutel geeft een melding om een nieuwe in te vullen.

## Voorbeeld

```yaml
action: todo.add_item
target:
  entity_id: todo.gezinstaken_huishouden
data:
  item: Stofzuiger legen
  due_date: "{{ now().date() }}"
```

## Tests

Integratietests tegen een draaiende webapp (Python 3.13):

```bash
uv venv --python 3.13 .venv && uv pip install --python .venv pytest-homeassistant-custom-component
GZT_URL=http://127.0.0.1:3010 GZT_KEY=gzt_... .venv/bin/pytest -p no:cacheprovider
```
