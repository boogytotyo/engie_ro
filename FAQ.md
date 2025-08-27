
### `FAQ.md`
# Depanare / Întrebări frecvente (FAQ)

## 1) Entitatea apare cu sufixul „_2”
**Cauză:** același `entity_id` există deja în registrul de entități (poate fi ascuns/disabled).
**Soluție:** Settings → Devices & Services → **Entities** (bifează *Show hidden/disabled*) → șterge/redenumește entitatea veche; apoi redenumește noua entitate fără sufix.  
(Avansat: oprește HA și editează `/.storage/core.entity_registry`.)

## 2) „Invalid credentials” / 401
- Verifică email/parolă în portalul Engie (autentificare din browser).
- Dacă folosești token: s-ar putea să fi expirat; reîmprospătează.
- Reconfigurează integrarea din *Settings → Devices & Services*.

## 3) „Cannot connect” / „Timeout”
- Verifică accesul la Internet al Home Assistant (DNS/SSL/Proxy).
- Vezi *Settings → System → Logs*.
- Poate fi o problemă temporară la server; încearcă mai târziu.

## 4) „Rate limited” / 429
- Prea multe cereri într-un interval scurt. Așteaptă câteva minute.

## 5) `sensor.engie_index_curent` arată „Nu”, deși sunt în perioada de citire
- Verifică atributele `start_citire` și `end_citire`. State = „Da” doar dacă **astăzi** ∈ [start_citire, end_citire].
- Dacă `autocit` este activ sau fereastra nu a început/este închisă, state rămâne „Nu”.

## 6) Nu văd `attribution` în atribute
- Comportament intenționat: a fost **eliminat** din atributele tuturor senzorilor.

## 7) `sensor.engie_valoare_factura_restanta` e 0.0 dar știu că am restanțe
- Integrarea adună câmpurile `unpaid` din `data.invoices[].invoices[]` (endpoint `invoices/ballance-details`).
- Verifică în **Logs** dacă răspunsul API conține `unpaid`. Dacă nu, portalul poate raporta 0 în acel moment.
- Folosește cardul Markdown din README pentru a vedea lista (atribut `facturi_restante`).

## 8) Cum activez log-urile de debug?
În `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.engie_ro: debug
