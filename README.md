# Engie România – Integrare Home Assistant

[![Release](https://img.shields.io/github/v/release/boogytotyo/engie_ro?display_name=tag&sort=semver)](https://github.com/boogytotyo/engie_ro/releases)
[![Downloads](https://img.shields.io/github/downloads/boogytotyo/engie_ro/total.svg)](https://github.com/boogytotyo/engie_ro/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Integrare custom pentru **Home Assistant** care afișează datele tale de la **Engie România** (facturi, istoric index, date contract etc.).  
Funcționează prin autentificare la portalul Engie și interogarea API-urilor lor publice.

> Documentație oficială: acest fișier • Issues / întrebări: [GitHub Issues](https://github.com/boogytotyo/engie_ro/issues)

---

## ✨ Funcționalități

- **Arhivă facturi** – `sensor.engie_arhiva_facturi`
  - *State*: valoarea **ultimei facturi**.
  - *Atribute*: sume pe ultimele 12 luni (ex. `iulie: 51,99 lei`), separator `──────────`, `Plăți efectuate`, `Total suma achitată`, `attribution`.
- **Istoric index** – `sensor.engie_istoric_index`
  - *State*: **cel mai recent index**.
  - *Atribute*: `luna: index` pentru ultimele luni (descrescător).
- **Index curent** – `sensor.engie_index_curent`
  - *State*: ultimul index raportat.
  - *Atribute*: `autocit`, `permite_index`, `interval_citire: start – end`, meta.
- **Date utilizator/contract** – `sensor.engie_date_utilizator_contract`
  - *State*: **PA** (cod punct de facturare).
  - *Atribute*: `email`, `nume`, `telefon`, `adresa`, `poc_number`, `division`, `installation_number`, **`CONTRACT_ACCOUNT`**, **`PA`**, `last_update`, `attribution`.
- **Valoare factură restantă** – `sensor.engie_factura_restanta_valoare`
  - *State*: total restanțe; *atribut*: `unpaid_list` (listează restanțele brute).
- **Update entity** – `update.engie_romania_update`
  - *installed_version* din `manifest.json`, *latest_version* din **GitHub Releases**, `release_url`, `release_summary`.

> Integrările și entitățile pot avea nume „Friendly Name” localizate (RO/EN/DE/FR).

---

## 📦 Instalare

### A. Manual (rapid)
1. Descarcă ultimul release de aici: [Releases](https://github.com/boogytotyo/engie_ro/releases).
2. Copiază directorul `custom_components/engie_ro` în:
   - **Home Assistant OS / Supervised / Container**: `/config/custom_components/engie_ro/`
   - **Core (venv)**: `~/.homeassistant/custom_components/engie_ro/`
3. **Restart** Home Assistant.
4. **Settings → Devices & Services → Add Integration** → caută „**Engie România**”.

### B. HACS (opțional, ca *Custom Repository*)
1. HACS → **Integrations** → ⋮ **Custom repositories**.
2. Repository: `https://github.com/boogytotyo/engie_ro`, Category: **Integration**, **Add**.
3. Instalează „Engie România”, apoi **Restart** HA și **Add Integration**.

---

## 🔑 Autentificare: e-mail/parolă sau bearer token (avansat)

Integrarea suportă autentificare standard (e-mail/parolă). Pentru situațiile în care autentificarea clasică e blocată (ex. 2FA, schimbări temporare în portal), poți folosi token (tip Bearer) extras din aplicația/portalul Engie.

Recomandat pentru majoritatea utilizatorilor: e-mail + parolă.
Avansat (doar dacă știi ce faci): token Bearer. Tokenul expiră periodic și va trebui reîmprospătat.

### A) Autentificare standard (e-mail/parolă)
Instalează integrarea și apasă Add Integration → Engie România.
Introdu Email și Parola de la contul tău Engie.

Salvează.

### B) Autentificare cu token (avansat)
Cum obții tokenul din portalul web (cel mai simplu)
Autentifică-te în portalul Engie (browser desktop).
Deschide Developer Tools → Network (Ctrl+Shift+I / F12).
Reîncarcă pagina și filtrează după myservices sau invoices / index.
Alege un request → tab-ul Headers → secțiunea Request Headers.
Copiază valoarea din Authorization (formatul este Bearer <TOKEN>).

> **Notă:** nu publica tokenul, nu-l urca în GitHub. Dacă vrei să-l ții într-un fișier, folosește secrets.yaml și lipește tokenul acolo, nu direct în text. Tokenurile **sunt temporare**. Când expira, integrarea poate începe să dea erori `(401 invalid_auth)`.

---

## 🔐 Configurare

La adăugare, ți se cere **Email** și **Parola** (cele de la contul tău Engie).  
Dacă ai mai multe puncte de consum/contracte, integrarea le va detecta și mapează automat entitățile principale (PA/POC).

> **Conectivitate:** integrarea comunică cu API-urile Engie; ai nevoie de acces Internet din mediul unde rulează HA.

---

## ⚠️ Mesaje de eroare (mapare automată)

Integrarea convertește codurile HTTP în mesaje lizibile în dialogul de configurare:

| Cod | Mesaj UI              | Când apare                                     |
|-----|-----------------------|-----------------------------------------------|
| 401 | `invalid_auth`        | Credentiale incorecte / sesiune invalidă      |
| 408 | `timeout`             | API Engie nu a răspuns la timp                |
| 429 | `rate_limited`        | Prea multe cereri într-un interval scurt      |
| 5xx | `server_error`        | Probleme temporare la serverul Engie          |
| alt | `cannot_connect`      | Rețea/SSL/host down etc.                      |

Mesajele sunt traduse (RO/EN/DE/FR).

---

## 🧩 Exemplu în Lovelace

```yaml
type: entities
title: Engie
entities:
  - entity: sensor.engie_date_utilizator_contract
    name: PA (punct de facturare)
  - entity: sensor.engie_index_curent
  - entity: sensor.engie_istoric_index
  - entity: sensor.engie_arhiva_facturi
  - entity: sensor.engie_factura_restanta_valoare
  - entity: update.engie_romania_update
