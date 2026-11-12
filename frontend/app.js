// 画面は2面だけ: A面（気分を書く）と B面（選ばれた一曲）。
// サーバーから来た文字列はすべて textContent で入れる（HTMLとして解釈させない）。
// なぜその曲なのか（読み取った気分・選曲理由・選曲方法）は、APIは返すが画面には出さない。

const GENRE_LABELS = { jazz: "Jazz", pop: "Rock / Pop", classical: "Classical", other: "Traditional / Soundtrack" };

// B面は出典の小説の色に染まる。装丁から拾った色で、白地の上で文字として読める濃さにしてある。
const WORK_COLORS = {
  hitsuji: "#b8501c",
  slow_boat: "#1d5fa8",
  sekai_no_owari: "#b8334f",
  norwegian_wood: "#1f6b4f",
  dance: "#2459c4",
  nejimaki: "#1f3f8f",
  sputnik: "#a45a2a",
  kafka: "#3f6fa8",
  after_dark: "#2f4a5c",
  "1q84": "#3a7d34",
  tsukuru: "#63676e",
  onna_no_inai: "#8f6a08",
};

const $ = (id) => document.getElementById(id);
const form = $("mood-form");
const textarea = $("mood-text");
const submit = $("submit");
const statusEl = $("status");

// ---- API ----

async function requestSong(text) {
  const res = await fetch("/api/recommendations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, count: 1 }),
  });
  if (res.status === 429) throw new Error("リクエストが続いています。1分ほど待ってから、もう一度お試しください。");
  if (res.status === 422) throw new Error("気分を1〜500文字で書いてください。");
  if (!res.ok) throw new Error("うまく選べませんでした。少し時間をおいて、もう一度お試しください。");
  const data = await res.json();
  if (!data.songs.length) throw new Error("うまく選べませんでした。少し時間をおいて、もう一度お試しください。");
  return data;
}

// ---- 描画 ----

function showStatus(message, kind = "") {
  statusEl.textContent = message;
  statusEl.className = `status ${kind}`.trim();
}

/** 画像は外部サイトから読む。届くまで（届かなければずっと）文字だけの面を見せる。 */
function setImage(frame, img, url, alt) {
  frame.classList.remove("has-image");
  img.onload = () => frame.classList.add("has-image");
  img.onerror = () => frame.classList.remove("has-image");
  img.alt = url ? alt : "";
  if (url) img.src = url;
  else img.removeAttribute("src");
}

function renderAnswer(data, text) {
  const song = data.songs[0];
  const hasOriginal = song.title_original && song.title_original !== song.title;

  $("quote").textContent = `「${text}」`;

  $("genre").textContent = GENRE_LABELS[song.genre] ?? song.genre;
  $("song-title").textContent = song.title;
  $("song-original").textContent = hasOriginal ? song.title_original : "";
  $("song-artist").textContent = song.artist;

  $("song-work").textContent =
    `『${song.work.title}』` + (song.story ? ` 所収「${song.story}」` : "") + `　${song.work.year}年`;
  $("song-scene").textContent = song.scene;

  $("sleeve-title").textContent = song.title_original || song.title;
  $("sleeve-artist").textContent = GENRE_LABELS[song.genre] ?? "";
  $("book-title").textContent = song.work.title;
  setImage($("sleeve"), $("artwork"), song.artwork_url, `${song.title}（${song.artist}）のジャケット`);
  setImage($("book"), $("cover"), song.work.cover_url, `『${song.work.title}』の表紙`);

  $("listen").href = song.listen_url;
  $("source").href = song.source_url;
  $("apple").hidden = !song.apple_url;
  if (song.apple_url) $("apple").href = song.apple_url;
  $("unverified").hidden = song.verified;

  document.documentElement.style.setProperty("--work", WORK_COLORS[song.work.key] ?? "");
}

function turnTo(side) {
  const isAnswer = side === "answer";
  $("ask").hidden = isAnswer;
  $("answer").hidden = !isAnswer;
  $("side-letter").textContent = isAnswer ? "Side B" : "Side A";
  $("side-name").textContent = isAnswer ? "一曲" : "気分";
  if (!isAnswer) document.documentElement.style.removeProperty("--work");
  window.scrollTo({ top: 0 });
}

function fitTextarea() {
  textarea.style.height = "auto";
  textarea.style.height = `${textarea.scrollHeight}px`;
}

// ---- イベント ----

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submit.disabled) return;
  const text = textarea.value.trim();
  if (!text) {
    showStatus("まず、いまの気分をひとこと書いてみてください。", "error");
    textarea.focus();
    return;
  }
  submit.disabled = true;
  showStatus("レコード棚を探しています", "busy");
  try {
    renderAnswer(await requestSong(text), text);
    showStatus("");
    turnTo("answer");
    $("again").focus({ preventScroll: true });
  } catch (error) {
    showStatus(error.message, "error");
  } finally {
    submit.disabled = false;
  }
});

textarea.addEventListener("input", fitTextarea);

// Enter で送る。改行は Shift+Enter。日本語入力の変換確定の Enter では送らない。
textarea.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  form.requestSubmit();
});

$("examples").addEventListener("click", (event) => {
  if (event.target.tagName !== "BUTTON") return;
  textarea.value = event.target.textContent;
  fitTextarea();
  form.requestSubmit();
});

$("again").addEventListener("click", () => {
  turnTo("ask");
  fitTextarea();
  textarea.focus();
  textarea.select();
});
