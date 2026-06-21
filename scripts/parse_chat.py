#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parser del chat de WhatsApp (Gonzalo <> Ana Maria) -> data/stats.json

- Lee el zip directamente (zipfile), no descomprime a disco.
- Parsea _chat.txt (espanol, formato [D/MM/YY, HH:MM:SS] Remitente: mensaje).
- Calcula metricas agregadas + story_insights.
- NUNCA escribe el texto completo del chat; solo conteos/agregados y citas curadas
  (estas ultimas se dejan vacias para que Gonzalo las llene manualmente).

Uso:
    python scripts/parse_chat.py
"""

import json
import os
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta

# --- Rutas ---
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ZIP_PATH = r"C:\Users\gonza\Anita\WhatsApp Chat - Ana Maria De la Puente.zip"
OUT_PATH = os.path.join(ROOT, "data", "stats.json")

GONZA = "Gonzalo Vásquez"
ANITA = "Ana Maria De la Puente"

LTR = "‎"  # left-to-right mark que precede algunas lineas/medios

# Patron de inicio de mensaje: [6/02/18, 15:46:04] Nombre: texto
MSG_RE = re.compile(
    r"^‎?\[(\d{1,2})/(\d{1,2})/(\d{2}), (\d{1,2}):(\d{2}):(\d{2})\] ([^:]+?): (.*)$",
    re.DOTALL,
)

MEDIA_MARKERS = {
    "imagen omitida": "image",
    "audio omitido": "audio",
    "video omitido": "video",
    "sticker omitido": "sticker",
    "gif omitido": "gif",
    "multimedia omitido": "other",
    "multimedia omitida": "other",
}

# Emojis a analizar
EMOJIS = ["❤️", "\U0001f970", "\U0001f60d", "\U0001f495",
          "\U0001f496", "\U0001f618", "\U0001f979", "\U0001f60a"]
EMOJI_NAMES = {
    "❤️": "❤️", "\U0001f970": "🥰", "\U0001f60d": "😍",
    "\U0001f495": "💕", "\U0001f496": "💖", "\U0001f618": "😘",
    "\U0001f979": "🥹", "\U0001f60a": "😊",
}

# Terminos de cariño (regex con limites de palabra, case-insensitive sobre texto normalizado)
LOVE_TERMS = {
    "te amo": r"te amo",
    "te quiero": r"te quiero",
    "amor": r"\bamor\b",
    "mi amor": r"mi amor",
    "bebe": r"\bbeb[eé]\b",
    "gordo/gorda": r"\bgord[oa]\b",
    "vida": r"\bvida\b",
    "corazon": r"\bcoraz[oó]n\b",
}

# Candidatos a apodos / vocativos (para "nuestro idioma")
# (sin duplicados por tilde: norm() ya quita acentos)
NICKNAME_CANDIDATES = [
    "chini", "amor", "bebe", "gordo", "gorda", "vida", "corazon",
    "mi amor", "mi vida", "gordito", "gordita", "negra", "negro", "flaca",
    "flaco", "nena", "bb", "chiquita", "chiquito", "princesa", "reina",
]

# "chini" = como se llaman entre ellos (apodo principal). Tracking dedicado.
CHINI_RE = re.compile(r"\bchini\b")

LAUGH_RE = re.compile(r"(?:ja){2,}|(?:je){2,}|(?:ha){2,}", re.IGNORECASE)

# Temas relevantes -> lista de patrones
TOPICS = {
    "viaje": [r"\bviaj", r"\bvuelo", r"\bavi[oó]n", r"\bvacacion"],
    "peru": [r"\bper[uú]\b", r"\blima\b"],
    "familia": [r"\bfamilia", r"\bmam[aá]\b", r"\bpap[aá]\b", r"\bherman"],
    "boda": [r"\bboda\b", r"\bcasamiento\b"],
    "matrimonio": [r"\bmatrimoni", r"\bcasar", r"\bcasad", r"\besposa\b", r"\besposo\b"],
    "casa": [r"\bcasa\b", r"\bdeparta", r"\bmudan", r"\balquiler"],
    "hijos": [r"\bhij[oa]s?\b", r"\bbeb[eé]\b", r"\bembaraz"],
    "berkeley": [r"\bberkeley\b", r"\bhaas\b", r"\bmba\b"],
    "trabajo": [r"\btrabaj", r"\bchamba\b", r"\boficina\b", r"\bjefe\b"],
    "futuro": [r"\bfuturo\b", r"\bplan(?:es)?\b", r"\bsue[ñn]o"],
}

# Stopwords español (compacto pero util)
STOPWORDS = set("""
a al algo algunas algunos ante antes como con contra cual cuando de del desde donde
dos durante e el ella ellas ellos en entre era erais eramos eran eras eres es esa esas
ese eso esos esta estaba estaban estado estais estamos estan estar estas este esto estos
estoy fue fueron fui ha habia habian han hasta hay la las le les lo los mas me mi mis
mucho muchos muy nada ni no nos nosotras nosotros o os otra otras otro otros para pero poco
por porque que quien se sea sean si sin sobre su sus tambien tanto te tiene tienen toda
todas todo todos tu tus un una uno unos vosotras vosotros y ya yo
ese esa eh ah oh aja ahi alli aqui aca q d x xq tk tkm pq pa pe ps tb bn tmb
si sii ya yaa jaja jajaja jeje haha ok oka okey bueno bien buena buenas buenos dia dias
estaba estare estoy voy va van vas ir ido fui dale igual asi ash uy uf ay
""".split())

# Marcadores de sistema a ignorar (no son mensajes reales)
SYSTEM_HINTS = [
    "los mensajes y las llamadas están cifrados",
    "se eliminó este mensaje",
    "este mensaje fue eliminado",
    "cambiaste el código de seguridad",
]


def strip_invisibles(s):
    return s.replace(LTR, "").replace("‏", "").strip()


def norm(s):
    """minusculas + sin tildes para matching robusto."""
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def parse_messages(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith("_chat.txt"))
        raw = z.read(name).decode("utf-8")

    messages = []
    current = None
    for line in raw.split("\n"):
        line = line.rstrip("\r")
        m = MSG_RE.match(line)
        if m:
            if current is not None:
                messages.append(current)
            d, mo, y, h, mi, s, sender, text = m.groups()
            year = 2000 + int(y)
            try:
                dt = datetime(year, int(mo), int(d), int(h), int(mi), int(s))
            except ValueError:
                current = None
                continue
            current = {"dt": dt, "sender": sender.strip(), "text": text}
        else:
            # continuacion de mensaje multilinea
            if current is not None:
                current["text"] += "\n" + line
    if current is not None:
        messages.append(current)

    # filtrar mensajes de sistema y normalizar
    clean = []
    for msg in messages:
        if msg["sender"] not in (GONZA, ANITA):
            continue
        low = strip_invisibles(msg["text"]).lower()
        if any(h in low for h in SYSTEM_HINTS):
            continue
        clean.append(msg)
    return clean


def classify_media(text):
    t = strip_invisibles(text).lower()
    for marker, kind in MEDIA_MARKERS.items():
        if t == marker or t.startswith(marker):
            return kind
    return None


def fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def main():
    if not os.path.exists(ZIP_PATH):
        print("No se encontro el zip:", ZIP_PATH, file=sys.stderr)
        sys.exit(1)

    msgs = parse_messages(ZIP_PATH)
    msgs.sort(key=lambda m: m["dt"])
    total = len(msgs)
    if total == 0:
        print("No se parsearon mensajes.", file=sys.stderr)
        sys.exit(1)

    people = [GONZA, ANITA]
    label = {GONZA: "Gonzalo", ANITA: "Ana Maria"}

    # --- acumuladores ---
    per_person = {p: {"messages": 0, "words": 0} for p in people}
    media = {p: Counter() for p in people}
    emoji_counts = {p: Counter() for p in people}
    laughs = {p: 0 for p in people}
    laughs_year = defaultdict(lambda: {GONZA: 0, ANITA: 0})
    love = {term: {GONZA: 0, ANITA: 0} for term in LOVE_TERMS}
    love_compiled = {t: re.compile(p) for t, p in LOVE_TERMS.items()}
    love_year = {term: defaultdict(int) for term in LOVE_TERMS}
    first_love = {}  # term -> (dt, sender)
    first_emoji = None
    words = {p: Counter() for p in people}
    nickname_counts = {p: Counter() for p in people}
    chini = {GONZA: 0, ANITA: 0}
    chini_year = defaultdict(lambda: {GONZA: 0, ANITA: 0})
    chini_first = {}
    topics = {t: defaultdict(lambda: 0) for t in TOPICS}  # topic -> year -> count
    topics_compiled = {t: [re.compile(p) for p in pats] for t, pats in TOPICS.items()}
    topics_total = Counter()

    per_day = Counter()          # date -> nº mensajes
    per_year = Counter()
    per_month = Counter()        # "YYYY-MM"
    per_week = Counter()         # ISO "YYYY-Www"
    by_hour = {p: Counter() for p in people}
    by_weekday = {p: Counter() for p in people}
    hour_total = Counter()
    weekday_total = Counter()

    day_first_sender = {}        # date -> sender (quien inicia el dia)
    word_re = re.compile(r"[a-zñáéíóúü]+", re.IGNORECASE)

    prev = None
    response_times = {p: [] for p in people}  # segundos, cuando cambia el emisor
    ICE_GAP = 6 * 3600  # 6h => "romper el hielo"
    ice_breaks = {p: 0 for p in people}

    for m in msgs:
        p = m["sender"]
        dt = m["dt"]
        d = dt.date()
        text = m["text"]
        ntext = norm(strip_invisibles(text))

        per_person[p]["messages"] += 1
        per_day[d] += 1
        per_year[dt.year] += 1
        per_month[dt.strftime("%Y-%m")] += 1
        iso = dt.isocalendar()
        per_week[f"{iso[0]}-W{iso[1]:02d}"] += 1
        by_hour[p][dt.hour] += 1
        hour_total[dt.hour] += 1
        by_weekday[p][dt.weekday()] += 1
        weekday_total[dt.weekday()] += 1

        if d not in day_first_sender:
            day_first_sender[d] = p

        kind = classify_media(text)
        if kind:
            media[p][kind] += 1
        else:
            # palabras (solo mensajes de texto reales)
            toks = word_re.findall(ntext)
            per_person[p]["words"] += len(toks)
            for w in toks:
                if len(w) >= 3 and w not in STOPWORDS:
                    words[p][w] += 1

        # emojis
        for e in EMOJIS:
            c = text.count(e)
            if c:
                emoji_counts[p][EMOJI_NAMES[e]] += c
                if first_emoji is None:
                    first_emoji = {"emoji": EMOJI_NAMES[e], "by": label[p], "when": fmt_dt(dt)}

        # risas
        if LAUGH_RE.search(ntext):
            laughs[p] += 1
            laughs_year[dt.year][p] += 1

        # amor
        for term, rx in love_compiled.items():
            if rx.search(ntext):
                love[term][p] += 1
                love_year[term][dt.year] += 1
                if term not in first_love:
                    first_love[term] = {"by": label[p], "when": fmt_dt(dt)}

        # "chini" (apodo principal)
        nchini = len(CHINI_RE.findall(ntext))
        if nchini:
            chini[p] += nchini
            chini_year[dt.year][p] += nchini
            if not chini_first:
                chini_first = {"by": label[p], "when": fmt_dt(dt)}

        # apodos candidatos
        for nk in NICKNAME_CANDIDATES:
            if re.search(r"\b" + re.escape(norm(nk)) + r"\b", ntext):
                nickname_counts[p][nk] += 1

        # temas
        for t, rxs in topics_compiled.items():
            if any(rx.search(ntext) for rx in rxs):
                topics[t][dt.year] += 1
                topics_total[t] += 1

        # tiempos de respuesta / ice break
        if prev is not None and prev["sender"] != p:
            delta = (dt - prev["dt"]).total_seconds()
            if 0 <= delta <= 24 * 3600:
                response_times[p].append(delta)
            if delta >= ICE_GAP:
                ice_breaks[p] += 1
        prev = m

    # --- rachas y brechas (sobre dias con mensajes) ---
    days_sorted = sorted(per_day.keys())
    longest_streak = 1
    cur_streak = 1
    streak_start = streak_end = days_sorted[0]
    best_start = best_end = days_sorted[0]
    longest_gap = 0
    gap_from = gap_to = None
    for i in range(1, len(days_sorted)):
        gap = (days_sorted[i] - days_sorted[i - 1]).days
        if gap == 1:
            cur_streak += 1
            streak_end = days_sorted[i]
            if cur_streak > longest_streak:
                longest_streak = cur_streak
                best_start, best_end = streak_start, streak_end
        else:
            cur_streak = 1
            streak_start = streak_end = days_sorted[i]
            if gap - 1 > longest_gap:
                longest_gap = gap - 1
                gap_from, gap_to = days_sorted[i - 1], days_sorted[i]

    # dias totales sin hablar (en el rango)
    total_span_days = (days_sorted[-1] - days_sorted[0]).days + 1
    days_silent = total_span_days - len(days_sorted)

    def stats_of(lst):
        if not lst:
            return {"mean": 0, "median": 0, "p90": 0, "n": 0}
        s = sorted(lst)
        n = len(s)
        mean = sum(s) / n
        median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
        p90 = s[min(n - 1, int(0.9 * n))]
        return {"mean": round(mean, 1), "median": round(median, 1),
                "p90": round(p90, 1), "n": n}

    top_days = per_day.most_common(10)
    most_active_month = per_month.most_common(1)[0]
    most_active_year = per_year.most_common(1)[0]
    romantic_month = Counter()
    # mes mas romantico = mas "te amo"
    # recomputar por mes para te amo
    # (rapido: re-scan ligero)
    for m in msgs:
        if love_compiled["te amo"].search(norm(strip_invisibles(m["text"]))):
            romantic_month[m["dt"].strftime("%Y-%m")] += 1
    rom_month = romantic_month.most_common(1)[0] if romantic_month else (None, 0)
    rom_year = max(love_year["te amo"].items(), key=lambda x: x[1]) if love_year["te amo"] else (None, 0)

    def who_more(d):
        g, a = d.get(GONZA, 0), d.get(ANITA, 0)
        return "Gonzalo" if g >= a else "Ana Maria"

    # mensaje mas largo (solo longitud + fecha + quien, sin texto completo)
    longest = max(msgs, key=lambda m: len(strip_invisibles(m["text"])) if not classify_media(m["text"]) else 0)
    longest_info = {
        "by": label[longest["sender"]],
        "when": fmt_dt(longest["dt"]),
        "chars": len(strip_invisibles(longest["text"])),
        "preview": strip_invisibles(longest["text"])[:120],
    }

    # --- construir stats ---
    stats = {
        "generated": {
            "source": "WhatsApp export",
            "total_messages": total,
            "total_words": sum(per_person[p]["words"] for p in people),
            "first_message": fmt_dt(msgs[0]["dt"]),
            "last_message": fmt_dt(msgs[-1]["dt"]),
            "days_talking": len(days_sorted),
            "calendar_span_days": total_span_days,
            "days_silent": days_silent,
            "per_person": {
                label[p]: {
                    "messages": per_person[p]["messages"],
                    "pct_messages": round(100 * per_person[p]["messages"] / total, 1),
                    "words": per_person[p]["words"],
                    "avg_words_per_msg": round(
                        per_person[p]["words"] / max(1, per_person[p]["messages"]), 2),
                } for p in people
            },
            "longest_streak_days": longest_streak,
            "longest_streak_range": [str(best_start), str(best_end)],
            "longest_gap_days": longest_gap,
            "longest_gap_range": [str(gap_from), str(gap_to)] if gap_from else None,
            "busiest_day": {"date": str(top_days[0][0]), "messages": top_days[0][1]},
            "top_10_days": [{"date": str(d), "messages": c} for d, c in top_days],
            "most_active_month": {"month": most_active_month[0], "messages": most_active_month[1]},
            "most_active_year": {"year": most_active_year[0], "messages": most_active_year[1]},
            "longest_message": longest_info,
            "love": {
                "terms": {
                    term: {
                        "total": love[term][GONZA] + love[term][ANITA],
                        "Gonzalo": love[term][GONZA],
                        "Ana Maria": love[term][ANITA],
                        "who_more": who_more(love[term]),
                        "first": first_love.get(term),
                    } for term in LOVE_TERMS
                },
                "first_heart_emoji": first_emoji,
                "most_romantic_month": {"month": rom_month[0], "te_amo": rom_month[1]},
                "most_romantic_year": {"year": rom_year[0], "te_amo": rom_year[1]},
            },
            "emojis": {
                "by_person": {label[p]: dict(emoji_counts[p].most_common()) for p in people},
                "totals": dict(sum((emoji_counts[p] for p in people), Counter()).most_common()),
            },
            "laughs": {
                "total": laughs[GONZA] + laughs[ANITA],
                "Gonzalo": laughs[GONZA],
                "Ana Maria": laughs[ANITA],
                "who_more": who_more(laughs),
                "by_year": {str(y): laughs_year[y] and
                            {"Gonzalo": laughs_year[y][GONZA], "Ana Maria": laughs_year[y][ANITA]}
                            for y in sorted(laughs_year)},
            },
            "media": {
                label[p]: dict(media[p]) for p in people
            },
            "media_totals": dict(sum((media[p] for p in people), Counter())),
            "activity": {
                "by_hour_total": {str(h): hour_total.get(h, 0) for h in range(24)},
                "by_weekday_total": {str(w): weekday_total.get(w, 0) for w in range(7)},
                "by_hour": {label[p]: {str(h): by_hour[p].get(h, 0) for h in range(24)} for p in people},
                "by_weekday": {label[p]: {str(w): by_weekday[p].get(w, 0) for w in range(7)} for p in people},
                "day_initiator": {
                    "Gonzalo": sum(1 for s in day_first_sender.values() if s == GONZA),
                    "Ana Maria": sum(1 for s in day_first_sender.values() if s == ANITA),
                },
                "ice_breaker_after_6h": {
                    "Gonzalo": ice_breaks[GONZA], "Ana Maria": ice_breaks[ANITA],
                },
                "response_time_seconds": {
                    label[p]: stats_of(response_times[p]) for p in people
                },
            },
            "rhythm": {
                "by_year": {str(y): per_year[y] for y in sorted(per_year)},
                "by_month": {m: per_month[m] for m in sorted(per_month)},
                "by_week": {w: per_week[w] for w in sorted(per_week)},
            },
            "personality": {
                "top_words": {label[p]: words[p].most_common(40) for p in people},
            },
            "our_language": {
                "nicknames": {label[p]: nickname_counts[p].most_common(15) for p in people},
                "chini": {
                    "note": "Así se llaman entre ellos — su apodo.",
                    "total": chini[GONZA] + chini[ANITA],
                    "Gonzalo": chini[GONZA],
                    "Ana Maria": chini[ANITA],
                    "who_more": who_more(chini),
                    "first": chini_first or None,
                    "by_year": {str(y): {"Gonzalo": chini_year[y][GONZA],
                                          "Ana Maria": chini_year[y][ANITA]}
                                for y in sorted(chini_year)},
                },
            },
            "data_note": {
                "gap_2022_2023": {
                    "from": str(gap_from) if gap_from else None,
                    "to": str(gap_to) if gap_to else None,
                    "days": longest_gap,
                    "explanation": ("Tramo casi sin mensajes por cambio de celular / "
                                    "export incompleto de WhatsApp, NO por silencio real. "
                                    "No usar como métrica de 'distancia'."),
                },
            },
            "topics": {
                "totals": dict(topics_total.most_common()),
                "by_year": {t: {str(y): topics[t][y] for y in sorted(topics[t])} for t in TOPICS},
            },
        },
        "story_insights": [],  # se llena abajo
        # NOTA: el contenido curado (capítulos, citas, momentos) vive en
        # data/curated.json para que NO se sobrescriba al regenerar.
    }

    # --- story insights automaticos ---
    g = stats["generated"]
    ins = []

    def emoji_top(person):
        c = emoji_counts[GONZA if person == "Gonzalo" else ANITA]
        return c.most_common(1)[0] if c else None

    weekday_names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    fav_weekday = weekday_total.most_common(1)[0][0]
    fav_hour = hour_total.most_common(1)[0][0]
    yr_items = sorted(per_year.items())

    ins.append(f"Se han escrito {total:,} mensajes en total.".replace(",", "."))
    ins.append(f"{g['most_active_year']['year']} fue el año con más mensajes "
               f"({g['most_active_year']['messages']:,}).".replace(",", "."))
    top_writer = max(people, key=lambda p: per_person[p]["messages"])
    ins.append(f"{label[top_writer]} escribió el {g['per_person'][label[top_writer]]['pct_messages']}% "
               f"de los mensajes.")
    ins.append(f"El día con más mensajes fue {g['busiest_day']['date']} con "
               f"{g['busiest_day']['messages']:,} mensajes.".replace(",", "."))
    ins.append(f"La racha más larga hablando todos los días fue de {longest_streak} días "
               f"({best_start} a {best_end}).")
    if chini[GONZA] + chini[ANITA]:
        ins.append(f"'Chini' —como se llaman entre ellos— aparece "
                   f"{chini[GONZA] + chini[ANITA]:,} veces y es la palabra #1 de los dos."
                   .replace(",", "."))
    ins.append(f"'Te amo' aparece {love['te amo'][GONZA] + love['te amo'][ANITA]:,} veces; "
               f"lo dice más {who_more(love['te amo'])}.".replace(",", "."))
    ins.append(f"'Te quiero' aparece {love['te quiero'][GONZA] + love['te quiero'][ANITA]} veces.")
    ins.append(f"La palabra 'amor' aparece {love['amor'][GONZA] + love['amor'][ANITA]:,} veces."
               .replace(",", "."))
    if first_love.get("te amo"):
        ins.append(f"El primer 'te amo' lo dijo {first_love['te amo']['by']} el "
                   f"{first_love['te amo']['when'][:10]}.")
    ins.append(f"Se rieron juntos {laughs[GONZA] + laughs[ANITA]:,} veces (mensajes con jaja/jeje); "
               f"ríe más {who_more(laughs)}.".replace(",", "."))
    ins.append(f"El día favorito para hablar fue el {weekday_names[fav_weekday]}.")
    ins.append(f"La hora pico de conversación es alrededor de las {fav_hour}:00.")
    mt = stats["generated"]["media_totals"]
    if mt.get("image"):
        ins.append(f"Compartieron {mt['image']:,} imágenes.".replace(",", "."))
    if mt.get("audio"):
        am = media[ANITA]["audio"]
        gm = media[GONZA]["audio"]
        tot = am + gm
        if tot:
            who = "Ana Maria" if am >= gm else "Gonzalo"
            pct = round(100 * max(am, gm) / tot)
            ins.append(f"{who} envió el {pct}% de los audios ({tot:,} en total)."
                       .replace(",", "."))
    di = g["activity"]["day_initiator"]
    starter = "Gonzalo" if di["Gonzalo"] >= di["Ana Maria"] else "Ana Maria"
    ins.append(f"{starter} fue quien más veces inició la conversación del día "
               f"({di[starter]:,} días).".replace(",", "."))
    rt = g["activity"]["response_time_seconds"]
    faster = min(people, key=lambda p: rt[label[p]]["median"] or 1e9)
    ins.append(f"{label[faster]} responde más rápido "
               f"(mediana {int(rt[label[faster]]['median'])}s).")
    if rom_month[0]:
        ins.append(f"El mes más romántico fue {rom_month[0]} con {rom_month[1]} 'te amo'.")
    # emojis favoritos
    for person in ("Gonzalo", "Ana Maria"):
        et = emoji_top(person)
        if et:
            ins.append(f"El emoji favorito de {person} es {et[0]} ({et[1]:,} veces)."
                       .replace(",", "."))
    # crecimiento ano a ano
    if len(yr_items) >= 2:
        first_y, last_y = yr_items[0], yr_items[-1]
        ins.append(f"En {first_y[0]} se escribieron {first_y[1]:,} mensajes; "
                   f"el chat arrancó ese año.".replace(",", "."))
    # temas
    for t, c in topics_total.most_common(5):
        ins.append(f"El tema '{t}' se menciona {c:,} veces a lo largo del chat."
                   .replace(",", "."))
    # apodo top compartido
    shared_nick = (nickname_counts[GONZA] + nickname_counts[ANITA]).most_common(1)
    if shared_nick:
        ins.append(f"El apodo más usado entre los dos es '{shared_nick[0][0]}' "
                   f"({shared_nick[0][1]:,} veces).".replace(",", "."))
    ins.append(f"Llevan {total_span_days:,} días desde el primer mensaje, "
               f"hablando en {len(days_sorted):,} de ellos.".replace(",", "."))
    ins.append(f"El mensaje más largo tiene {longest_info['chars']:,} caracteres "
               f"(de {longest_info['by']}).".replace(",", "."))

    stats["story_insights"] = ins

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"OK -> {OUT_PATH}")
    print(f"Mensajes: {total:,}".replace(",", "."))
    print(f"Insights generados: {len(ins)}")


if __name__ == "__main__":
    main()
