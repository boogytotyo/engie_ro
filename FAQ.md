# Depanare / Întrebări frecvente (FAQ)

## 1) Entitatea apare cu sufixul „_2”
**Cauză:** același `entity_id` există deja în registrul de entități (chiar dacă e ascuns/dezactivat).  
**Soluție:** Settings → Devices & Services → **Entities** (bifează *Show hidden/disabled*) → șterge entitatea veche sau redenumește‑o; apoi editează noua entitate și scoate sufixul.  
(Avansat: oprește HA și editează `/.storage/core.entity_registry`).

## 2) „Invalid credentials” / 401
- Verifică emailul/parola în portalul Engie (autentificare din browser).  
- Asigură‑te că nu este activ un mecanism suplimentar (2FA/recaptcha) care blochează API.  
- Reconfigurează integrarea din *Settings → Devices & Services*.

## 3) „Cannot connect” / „Timeout”
- Verifică dacă Home Assistant are ieșire la Internet (DNS/SSL/Proxy).  
- Vezi *Settings → System → Logs* pentru detalii.  
- Reîncearcă mai târziu — poate fi o problemă temporară la serverul Engie.

## 4) „Rate limited” / 429
- Au fost făcute prea multe cereri într‑un interval scurt. Așteaptă câteva minute și încearcă din nou.

## 5) Lipsesc atribute sau valori
- Repornește Home Assistant.  
- Verifică dacă sesiunea a expirat și reconfigurează integrarea (reintrodu user/parola).

## 6) Cum activez log‑urile de debug?
În `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.engie_ro: debug
```
Apoi, în *Developer Tools → Services* → `logger.set_level`, setează `custom_components.engie_ro: debug`.

## 7) Entitatea de update nu arată ultima versiune
- În `custom_components/engie_ro/update.py` setează `REPO = "boogytotyo/engie_ro"`.  
- Repornește Home Assistant și verifică `update.engie_romania_update`.

## 8) Cum dezinstalez complet integrarea?
- *Settings → Devices & Services* → **Remove Integration**.  
- Oprește Home Assistant și, opțional, șterge directorul `/config/custom_components/engie_ro` și intrările aferente din `/config/.storage` (doar dacă știi ce faci).
