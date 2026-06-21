// Nosotros — carga stats.json + curated.json y arma la experiencia.
const MESES = ["enero","febrero","marzo","abril","mayo","junio","julio",
  "agosto","septiembre","octubre","noviembre","diciembre"];

const fmtInt = (n) => Math.round(n).toLocaleString("es-PE");

function fmtFecha(iso) {           // "2018-02-06 15:46:04" -> "6 feb 2018"
  const [d] = iso.split(" ");
  const [y, m, day] = d.split("-").map(Number);
  return `${day} ${MESES[m - 1].slice(0, 3)} ${y}`;
}

function diffYM(isoA, isoB) {       // -> "8 años, 4 meses"
  const a = new Date(isoA.replace(" ", "T"));
  const b = new Date(isoB.replace(" ", "T"));
  let months = (b.getFullYear() - a.getFullYear()) * 12 + (b.getMonth() - a.getMonth());
  if (b.getDate() < a.getDate()) months -= 1;
  const y = Math.floor(months / 12), mo = months % 12;
  const yStr = `${y} año${y !== 1 ? "s" : ""}`;
  const mStr = mo > 0 ? `, ${mo} mes${mo !== 1 ? "es" : ""}` : "";
  return `${yStr}${mStr}`;
}

// ---------- count-up ----------
function countUp(el, target) {
  const dur = 1600, start = performance.now();
  const ease = (t) => 1 - Math.pow(1 - t, 3);
  function step(now) {
    const t = Math.min(1, (now - start) / dur);
    el.textContent = fmtInt(target * ease(t));
    if (t < 1) requestAnimationFrame(step);
    else el.textContent = fmtInt(target);
  }
  requestAnimationFrame(step);
}

// ---------- reveal + count on scroll ----------
function setupObserver() {
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      e.target.classList.add("in");
      // contar números: el propio elemento y/o sus descendientes
      const counters = [];
      if (e.target.hasAttribute("data-count")) counters.push(e.target);
      e.target.querySelectorAll?.("[data-count]").forEach((el) => counters.push(el));
      counters.forEach((el) => {
        if (el.dataset.done) return;
        el.dataset.done = "1";
        countUp(el, +el.dataset.target || 0);
      });
      // barras versus
      e.target.querySelectorAll?.("[data-bar]").forEach((el) => {
        el.style.width = el.dataset.bar + "%";
      });
      io.unobserve(e.target);
    });
  }, { threshold: 0.25 });
  document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
}

// ---------- progress bar ----------
window.addEventListener("scroll", () => {
  const h = document.documentElement;
  const p = (h.scrollTop / (h.scrollHeight - h.clientHeight)) * 100;
  document.getElementById("progress").style.width = p + "%";
});

// ---------- main ----------
async function main() {
  const [stats, curated] = await Promise.all([
    fetch("data/stats.json").then((r) => r.json()),
    fetch("data/curated.json").then((r) => r.json()).catch(() => ({})),
  ]);
  const g = stats.generated;

  const setTarget = (id, v) => { const el = document.getElementById(id); if (el) el.dataset.target = v; };
  const setText = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

  // 1. Hero
  setText("hero-time", diffYM(g.first_message, g.last_message) + " y contando.");
  setTarget("hero-total", g.total_messages);

  // 2. Inicio — primer mensaje, días, horas escritas
  setText("first-date", fmtFecha(g.first_message));
  setTarget("days-talking", g.days_talking);
  // tiempo estimado escribiéndonos: palabras / velocidad de tipeo en celular (~30 ppm)
  const WPM = 30;
  const horas = Math.round(g.total_words / WPM / 60 / 10) * 10;
  const dias = Math.round(g.total_words / WPM / 60 / 24);
  setText("timespent-num", `≈ ${fmtInt(horas)} h`);
  setText("timespent-txt", `escribiéndonos · más de ${dias} días tecleando`);

  // 3. Versus — tabla de doble entrada
  const gm = g.per_person["Gonzalo"], am = g.per_person["Ana Maria"];
  setText("t-g-msgs", fmtInt(gm.messages));
  setText("t-a-msgs", fmtInt(am.messages));
  setText("t-g-pct", gm.pct_messages + "%");
  setText("t-a-pct", am.pct_messages + "%");
  setText("t-g-words", fmtInt(gm.words));
  setText("t-a-words", fmtInt(am.words));
  setText("t-g-avg", gm.avg_words_per_msg);
  setText("t-a-avg", am.avg_words_per_msg);
  setText("versus-note",
    `Yo mando más mensajes, pero Anita escribe más largo: ${am.avg_words_per_msg} palabras por mensaje frente a ${gm.avg_words_per_msg}.`);

  // 4. Ritmo — facts como cuadritos + heatmap
  const weekdays = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"];
  const favDay = Object.entries(g.activity.by_weekday_total).sort((a,b)=>b[1]-a[1])[0][0];
  const favHour = Object.entries(g.activity.by_hour_total).sort((a,b)=>b[1]-a[1])[0][0];
  const di = g.activity.day_initiator;
  const rt = g.activity.response_time_seconds;
  setText("fav-day", weekdays[+favDay]);
  setText("fav-hour", `${favHour}:00`);
  setText("who-starts", di["Gonzalo"] >= di["Ana Maria"] ? "Gonza" : "Anita");
  setText("who-fast", rt["Gonzalo"].median <= rt["Ana Maria"].median ? "Gonza" : "Anita");
  buildHeat(g.activity.by_hour_total);

  // 5. Amor
  const love = g.love.terms;
  setTarget("teamo-count", love["te amo"].total);
  setTarget("amor-count", love["amor"].total);
  setTarget("tequiero-count", love["te quiero"].total);
  const hearts = Object.values(g.emojis.totals).reduce((a,b)=>a+b,0);
  const heartsEl = document.getElementById("hearts-count");
  heartsEl.dataset.target = hearts; heartsEl.dataset.count = "";
  setText("love-note",
    `El primer “te amo” lo dijo ${love["te amo"].first.by} el ${fmtFecha(love["te amo"].first.when)}. ` +
    `Hoy lo decimos más de mil veces.`);

  // 6. Chini + ranking de palabras nuestras + temas
  const chini = g.our_language.chini;
  setText("chini-note",
    `Así nos llamamos. Lo dijimos por primera vez ${chini.first ? "el " + fmtFecha(chini.first.when) : "hace años"} y no paramos: ${fmtInt(chini.total)} veces.`);
  buildWordRank(chini, love);
  buildTopics(g.topics.totals);

  // 7. Multimedia
  const mt = g.media_totals;
  setTarget("m-images", mt.image || 0);
  setTarget("m-audios", mt.audio || 0);
  setTarget("m-stickers", mt.sticker || 0);
  setTarget("m-videos", mt.video || 0);

  // Racha (cerca del final): la MÁS LARGA
  setTarget("streak-days", g.longest_streak_days);
  const pct = Math.round(100 * g.days_talking / g.calendar_span_days);
  setText("streak-range",
    `Nuestra racha más larga: del ${fmtFecha(g.longest_streak_range[0])} al ${fmtFecha(g.longest_streak_range[1])}, sin fallar un solo día. ` +
    `Y en ocho años hablamos ${fmtInt(g.days_talking)} de ${fmtInt(g.calendar_span_days)} días — el ${pct}% del tiempo.`);

  // 9. Capítulos
  buildChapters(curated.chapters || []);

  // Insights
  buildInsights(stats.story_insights || []);

  // Final
  if (curated.closing) {
    setText("closing-title", curated.closing.title);
    setText("closing-sub", curated.closing.subtitle);
    setText("closing-sig", curated.closing.signature);
  }
  setText("closing-date", fmtFecha(g.last_message).toUpperCase());

  setupObserver();
}

function buildHeat(byHour) {
  const wrap = document.getElementById("hour-heat");
  const vals = Object.values(byHour);
  const max = Math.max(...vals);
  for (let h = 0; h < 24; h++) {
    const v = byHour[h] || 0;
    const t = v / max;
    const cell = document.createElement("div");
    cell.className = "cell";
    // interpolar rose-soft -> coral
    const r = Math.round(247 + t * (212 - 247));
    const gg = Math.round(230 + t * (113 - 230));
    const b = Math.round(225 + t * (92 - 225));
    cell.style.background = `rgb(${r},${gg},${b})`;
    cell.title = `${h}:00 — ${fmtInt(v)} mensajes`;
    wrap.appendChild(cell);
  }
}

const SHORT = (n) => (n === "Ana Maria" ? "Anita" : "Gonza");

function buildWordRank(chini, love) {
  const rows = [{ w: "chini", total: chini.total, who: chini.who_more }];
  Object.entries(love).forEach(([k, v]) => rows.push({ w: k, total: v.total, who: v.who_more }));
  rows.sort((a, b) => b.total - a.total);
  const tb = document.querySelector("#word-rank tbody");
  rows.slice(0, 8).forEach((r, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="rk">${i + 1}</td><td class="rw">“${r.w}”</td>` +
      `<td>${fmtInt(r.total)}</td><td class="${r.who === "Ana Maria" ? "th-a" : "th-g"}">${SHORT(r.who)}</td>`;
    tb.appendChild(tr);
  });
}

const TOPIC_LABEL = {
  casa: "Casa", familia: "Familia", futuro: "Futuro", trabajo: "Trabajo",
  viaje: "Viajes", peru: "Perú", berkeley: "Berkeley", hijos: "Hijos",
  matrimonio: "Matrimonio", boda: "Boda",
};
function buildTopics(totals) {
  const wrap = document.getElementById("topic-pills");
  Object.entries(totals)
    .filter(([, c]) => c >= 100)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .forEach(([k, c]) => {
      const span = document.createElement("span");
      span.className = "pill";
      span.innerHTML = `${TOPIC_LABEL[k] || k}<b>${fmtInt(c)}</b>`;
      wrap.appendChild(span);
    });
}

function buildChapters(chapters) {
  const wrap = document.getElementById("chapters");
  chapters.forEach((c, i) => {
    const div = document.createElement("div");
    div.className = "chapter reveal" + (i % 3 ? ` d${i % 3}` : "");
    div.innerHTML = `<div class="cemoji">${c.emoji || "•"}</div>
      <div><div class="cyear">${c.year || ""}</div><h3>${c.title}</h3><p>${c.text || ""}</p></div>`;
    wrap.appendChild(div);
  });
}

function buildInsights(list) {
  const ul = document.getElementById("insights");
  list.forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    ul.appendChild(li);
  });
}

main().catch((e) => {
  console.error(e);
  document.getElementById("hero-time").textContent = "No pude cargar los datos 😢";
});
