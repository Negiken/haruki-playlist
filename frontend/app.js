// 画面の役割は3つだけ: 入力を送る / 結果を描く / 収録作品を出す。
// サーバーから来た文字列はすべて textContent で入れる（HTMLとして解釈させない）。

const GENRE_LABELS = { jazz: "ジャズ", pop: "ロック / ポップス", classical: "クラシック", other: "その他" };
const ENGINE_LABELS = { claude: "Claude が選曲", rules: "キーワードで選曲" };

const $ = (id) => document.getElementById(id);
const form = $("mood-form");
const textarea = $("mood-text");
const submit = $("submit");
const statusEl = $("status");

// ---- API ----

async function requestRecommendations(text) {
  const res = await fetch("/api/recommendations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (res.ok) return res.json();
  if (res.status === 429) throw new Error("リクエストが続いています。1分ほど待ってから、もう一度お試しください。");
  if (res.status === 422) throw new Error("気分を1〜500文字で入力してください。");
  throw new Error("うまく選曲できませんでした。少し時間をおいて、もう一度お試しください。");
}

// ---- 描画 ----

function showStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
  statusEl.hidden = !message;
}

function renderResult(data) {
  $("mood-summary").textContent = data.mood.summary;
  $("engine").textContent = ENGINE_LABELS[data.engine] ?? "";

  const tags = $("mood-tags");
  tags.replaceChildren(
    ...data.mood.tags.map((tag) => {
      const el = document.createElement("span");
      el.className = "tag";
      el.textContent = tag.label;
      return el;
    })
  );

  $("songs").replaceChildren(...data.songs.map(renderSong));
  $("result").hidden = false;
}

function renderSong(song) {
  const node = $("song-template").content.cloneNode(true);
  const q = (sel) => node.querySelector(sel);

  q(".song-title").textContent = song.title;
  q(".genre").textContent = GENRE_LABELS[song.genre] ?? song.genre;
  q(".song-artist").textContent =
    song.title_original && song.title_original !== song.title
      ? `${song.artist} — ${song.title_original}`
      : song.artist;
  q(".song-reason").textContent = song.reason;
  q(".song-work").textContent =
    `『${song.work.title}』（${song.work.year}年）` + (song.story ? ` 所収「${song.story}」` : "");
  q(".song-scene").textContent = song.scene;
  q(".listen").href = song.listen_url;
  q(".source").href = song.source_url;
  q(".unverified").hidden = song.verified;
  return node;
}

async function renderWorks() {
  try {
    const works = await (await fetch("/api/works")).json();
    $("works").replaceChildren(
      ...works.map((w) => {
        const li = document.createElement("li");
        li.textContent = `『${w.title}』（${w.year}年）`;
        const count = document.createElement("span");
        count.className = "count";
        count.textContent = `${w.song_count}曲`;
        li.append(count);
        return li;
      })
    );
  } catch {
    // 一覧は補足情報なので、取れなくても画面は使える
  }
}

// ---- イベント ----

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = textarea.value.trim();
  if (!text) {
    showStatus("まず、いまの気分を書いてみてください。", true);
    textarea.focus();
    return;
  }
  submit.disabled = true;
  showStatus("レコード棚を探しています…");
  try {
    renderResult(await requestRecommendations(text));
    showStatus("");
    $("result").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    submit.disabled = false;
  }
});

textarea.addEventListener("input", () => {
  $("char-count").textContent = `${textarea.value.length} / 500`;
});

$("chips").addEventListener("click", (event) => {
  if (!event.target.classList.contains("chip")) return;
  textarea.value = event.target.textContent;
  textarea.dispatchEvent(new Event("input"));
  form.requestSubmit();
});

renderWorks();
