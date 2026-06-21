# Nosotros 💬❤️

> La historia que fuimos escribiendo sin darnos cuenta.

Una web interactiva tipo *Spotify Wrapped* construida a partir del export completo
de un chat de WhatsApp. Convierte 265 mil mensajes en una narrativa romántica:
cuánto nos escribimos, cuántas veces dijimos "te amo", nuestro idioma ("chini"),
nuestras risas, nuestros años… contado como una historia, no como un dashboard.

## 🔒 Privacidad (importante)

El chat es íntimo. **Nunca** se sube el chat crudo a GitHub.

- El parser corre **en local** y genera solo un archivo **agregado**: `data/stats.json`
  (conteos y métricas, sin el historial de mensajes).
- `data/curated.json` contiene el contenido editable a mano (capítulos, citas que tú elijas).
- `.gitignore` bloquea `_chat.txt`, `*.zip`, `*.txt` y carpetas privadas.

> Aun así, revisa `data/stats.json` antes de publicar: por decisión propia incluye
> un *preview* del mensaje más largo. Si algún día prefieres quitarlo, edita
> `longest_message.preview` o ajústalo en el parser.

## 🚀 Uso

### 1. Generar los datos (local)

```bash
python scripts/parse_chat.py
```

Lee el zip definido en `scripts/parse_chat.py` (`ZIP_PATH`) y escribe `data/stats.json`.

### 2. Ver la web

Es estática. Necesita un servidor local (por el `fetch` del JSON):

```bash
python -m http.server 8000
# abrir http://localhost:8000
```

### 3. Publicar en GitHub Pages

1. Crea un repo y sube **todo menos** lo ignorado (el chat crudo se queda en tu PC).
2. Settings → Pages → Branch `main` / carpeta `/root`.
3. Listo: la web sirve `index.html` y lee `data/stats.json`.

## ✏️ Personalizar

- **Capítulos / hitos**: edita `data/curated.json` (`chapters`). El parser nunca lo toca.
- **Cierre y firma**: `curated.json` → `closing`.
- **Estética**: variables CSS al inicio de `styles.css` (`--coral`, `--gold`, etc.).

## 📁 Estructura

```
nosotros/
├── index.html          # estructura de las pantallas
├── styles.css          # estética (crema / coral / dorado, Playfair + Inter)
├── app.js              # carga datos, count-up, scroll-reveal, gráficos
├── scripts/
│   └── parse_chat.py   # parser local del chat -> data/stats.json
└── data/
    ├── stats.json      # métricas agregadas (generado)
    └── curated.json    # contenido editable a mano
```

Hecho con cariño. Gonzalo ❤️ Anita
