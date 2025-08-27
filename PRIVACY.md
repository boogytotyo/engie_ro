
---

### `PRIVACY.md`
```markdown
# Politica de confidențialitate (Integrare locală)

Această integrare personalizată pentru **Home Assistant** rulează **local** pe instanța ta Home Assistant.  
Nu este un serviciu cloud și **nu trimite** date către terți, în afară de endpoint-urile oficiale **Engie România** pe care le interoghează la cererea ta.

## Ce date sunt prelucrate
- Datele de autentificare la contul Engie (email și parolă) sau **token** (opțional, avansat).
- Metadate despre cont/contract și informații de consum/facturare returnate de Engie (PA/POC, Contract Account, facturi, indexuri etc.).

## Unde sunt stocate datele
- Credentialele și tokenurile sunt stocate **în Config Entries** ale Home Assistant, pe dispozitivul tău (în `/config/.storage`).  
- Nu se transmite niciun fel de informație în altă parte, exceptând apelurile către API-ul Engie atunci când utilizezi integrarea.

## Jurnale (logs)
- Jurnalele sunt scrise local de Home Assistant și pot include detalii de eroare (coduri HTTP, mesaje).  
- Poți activa/dezactiva logarea de tip debug în orice moment (vezi `FAQ.md`).

## Păstrarea și ștergerea datelor
- Toate datele rămân pe sistemul tău Home Assistant.  
- Pentru a le elimina: **șterge integrarea** din *Settings → Devices & Services*, apoi, opțional, oprește HA și șterge manual fișierele aferente din `/config/.storage` (doar dacă știi ce faci).

## Servicii terțe
- Integrarea comunică **doar** cu endpoint-urile **Engie România** pentru a prelua informațiile contului (ex.: `invoices/ballance-details`, `invoices/history-only`, `index/*`).  
- Dacă activezi opțional entitatea de **update**, aceasta interoghează **GitHub Releases** pentru a verifica cea mai nouă versiune a integrării.

## Contact
- Întrebări sau solicitări: deschide un *issue* în repository-ul GitHub al proiectului.
