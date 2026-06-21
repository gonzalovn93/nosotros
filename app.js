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
  // tiempo estimado escribiéndonos: palabras / velocidad de tipeo en celular (~30 ppm)
  const WPM = 30;
  const horas = g.total_words / WPM / 60;
  const dias = horas / 24;
  setText("hero-timespent",
    `Solo escribiendo, son unas ${fmtInt(Math.round(horas / 10) * 10)} horas juntos: ` +
    `más de ${Math.round(dias)} días sin parar de teclear.`);

  // 2. Inicio
  setText("first-date", fmtFecha(g.first_message));
  setText("last-date", fmtFecha(g.last_message));
  setTarget("days-talking", g.days_talking);

  // 3. Versus
  const gm = g.per_person["Gonzalo"], am = g.per_person["Ana Maria"];
  const maxm = Math.max(gm.messages, am.messages);
  setText("g-msgs", fmtInt(gm.messages));
  setText("a-msgs", fmtInt(am.messages));
  const gb = document.getElementById("g-bar"), ab = document.getElementById("a-bar");
  gb.dataset.bar = (100 * gm.messages / maxm).toFixed(1);
  ab.dataset.bar = (100 * am.messages / maxm).toFixed(1);
  gb.closest(".reveal").querySelectorAll(".bar > span").forEach(() => {});
  // animar barras al revelar la sección versus
  const versusSection = document.getElementById("s-versus");
  new IntersectionObserver((es, o) => es.forEach((e) => {
    if (e.isIntersecting) { gb.style.width = gb.dataset.bar + "%"; ab.style.width = ab.dataset.bar + "%"; o.disconnect(); }
  }), { threshold: 0.3 }).observe(versusSection);
  setText("versus-note",
    `Entre los dos, ${fmtInt(g.total_messages)} mensajes. Ana Maria escribe más largo (${am.avg_words_per_msg} palabras por mensaje vs ${gm.avg_words_per_msg}).`);

  // 4. Racha + heatmap horas
  setTarget("streak-days", g.longest_streak_days);
  setText("streak-range", `Del ${g.longest_streak_range[0]} al ${g.longest_streak_range[1]}, sin fallar un solo día.`);
  buildHeat(g.activity.by_hour_total);
  const weekdays = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"];
  const favDay = Object.entries(g.activity.by_weekday_total).sort((a,b)=>b[1]-a[1])[0][0];
  const favHour = Object.entries(g.activity.by_hour_total).sort((a,b)=>b[1]-a[1])[0][0];
  setText("rhythm-note", `Nuestro día favorito para hablar es el ${weekdays[+favDay]}, y la hora pico, las ${favHour}:00.`);

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

  // 6. Chini
  const chini = g.our_language.chini;
  setTarget("chini-total", chini.total);
  setTarget("laughs-total", g.laughs.total);
  setText("laughs-who", g.laughs.who_more);
  setText("chini-note",
    `Así nos llamamos. Lo dijimos por primera vez ${chini.first ? "el " + fmtFecha(chini.first.when) : "hace años"} y no paramos: ${fmtInt(chini.total)} veces.`);

  // 7. Multimedia
  const mt = g.media_totals;
  setTarget("m-images", mt.image || 0);
  setTarget("m-audios", mt.audio || 0);
  setTarget("m-stickers", mt.sticker || 0);
  setTarget("m-videos", mt.video || 0);

  // 8. Timeline por año
  buildYearChart(g.rhythm.by_year);

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

function buildYearChart(byYear) {
  const labels = Object.keys(byYear);
  const data = Object.values(byYear);
  const ctx = document.getElementById("yearChart");
  const grad = ctx.getContext("2d").createLinearGradient(0, 0, 0, 220);
  grad.addColorStop(0, "rgba(212,113,92,0.55)");
  grad.addColorStop(1, "rgba(212,113,92,0.02)");
  new Chart(ctx, {
    type: "line",
    data: { labels, datasets: [{
      data, fill: true, backgroundColor: grad,
      borderColor: "#d4715c", borderWidth: 2.5, tension: 0.4,
      pointBackgroundColor: "#c9a25e", pointRadius: 4, pointHoverRadius: 6,
    }] },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: (c) => `${fmtInt(c.parsed.y)} mensajes` } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#6b605a" } },
        y: { grid: { color: "rgba(107,96,90,0.08)" }, ticks: { color: "#6b605a", callback: (v) => fmtInt(v) } },
      },
    },
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
