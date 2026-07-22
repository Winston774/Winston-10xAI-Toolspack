"use strict";

const state = {
  words: [],
  activeTab: "library",
  currentCard: null,
  answerVisible: false
};

const elements = {};

document.addEventListener("DOMContentLoaded", init);

function init() {
  bindElements();
  bindEvents();
  loadData();
}

function bindElements() {
  elements.summary = document.querySelector("#summary");
  elements.settingsButton = document.querySelector("#settingsButton");
  elements.setupWarning = document.querySelector("#setupWarning");
  elements.captureButton = document.querySelector("#captureButton");
  elements.captureStatus = document.querySelector("#captureStatus");
  elements.tabList = document.querySelector(".tabs");
  elements.libraryTab = document.querySelector("#libraryTab");
  elements.reviewTab = document.querySelector("#reviewTab");
  elements.libraryPanel = document.querySelector("#libraryPanel");
  elements.reviewPanel = document.querySelector("#reviewPanel");
  elements.searchInput = document.querySelector("#searchInput");
  elements.exportJsonButton = document.querySelector("#exportJsonButton");
  elements.exportCsvButton = document.querySelector("#exportCsvButton");
  elements.emptyLibrary = document.querySelector("#emptyLibrary");
  elements.wordList = document.querySelector("#wordList");
  elements.emptyReview = document.querySelector("#emptyReview");
  elements.flashcard = document.querySelector("#flashcard");
  elements.cardStatus = document.querySelector("#cardStatus");
  elements.cardCount = document.querySelector("#cardCount");
  elements.cardRevealButton = document.querySelector("#cardRevealButton");
  elements.cardWord = document.querySelector("#cardWord");
  elements.cardHint = document.querySelector("#cardHint");
  elements.cardAnswer = document.querySelector("#cardAnswer");
  elements.cardPartOfSpeech = document.querySelector("#cardPartOfSpeech");
  elements.cardTranslation = document.querySelector("#cardTranslation");
  elements.learningButton = document.querySelector("#learningButton");
  elements.knownButton = document.querySelector("#knownButton");
  elements.nextButton = document.querySelector("#nextButton");
}

function bindEvents() {
  elements.settingsButton.addEventListener("click", () => sendRuntimeMessage({ type: "OPEN_OPTIONS" }));
  elements.captureButton.addEventListener("click", openCapturePanel);
  elements.libraryTab.addEventListener("click", () => switchTab("library"));
  elements.reviewTab.addEventListener("click", () => switchTab("review"));
  elements.tabList.addEventListener("keydown", handleTabKeydown);
  elements.searchInput.addEventListener("input", renderLibrary);
  elements.exportJsonButton.addEventListener("click", exportJson);
  elements.exportCsvButton.addEventListener("click", exportCsv);
  elements.wordList.addEventListener("click", handleWordListClick);
  elements.cardRevealButton.addEventListener("click", revealAnswer);
  elements.learningButton.addEventListener("click", () => markReview("learning"));
  elements.knownButton.addEventListener("click", () => markReview("known"));
  elements.nextButton.addEventListener("click", pickCard);

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local" && changes.gstWordBank) {
      state.words = Array.isArray(changes.gstWordBank.newValue) ? changes.gstWordBank.newValue : [];
      renderAll();
    }
  });
}

async function openCapturePanel() {
  elements.captureButton.disabled = true;
  elements.captureStatus.textContent = "";
  // Side Panel opening must happen synchronously inside the click gesture.
  const panelPromise = chrome.sidePanel.open({
    windowId: chrome.windows.WINDOW_ID_CURRENT
  });
  const tabsPromise = chrome.tabs.query({ active: true, lastFocusedWindow: true });
  try {
    const [, tabs] = await Promise.all([panelPromise, tabsPromise]);
    const tab = tabs[0];
    if (!tab?.id || !Number.isInteger(tab.windowId)) {
      throw new Error("找不到目前的分頁。");
    }
    const response = await sendRuntimeMessage({
      type: "OPEN_CAPTURE_PANEL",
      tabId: tab.id,
      windowId: tab.windowId
    });
    if (!response?.ok) {
      throw new Error(response?.message || "無法建立框選工作。");
    }
    window.close();
  } catch (error) {
    elements.captureButton.disabled = false;
    elements.captureStatus.textContent = error?.message || "無法開啟畫面文字面板。";
  }
}

async function loadData() {
  const [settings, wordBank] = await Promise.all([
    sendRuntimeMessage({ type: "GET_SETTINGS_STATUS" }),
    sendRuntimeMessage({ type: "GET_WORD_BANK" })
  ]);

  elements.setupWarning.hidden = Boolean(settings?.hasApiKey);
  state.words = Array.isArray(wordBank?.words) ? wordBank.words : [];
  renderAll();
}

function switchTab(tab) {
  state.activeTab = tab;
  const isLibrary = tab === "library";
  elements.libraryTab.classList.toggle("active", isLibrary);
  elements.reviewTab.classList.toggle("active", !isLibrary);
  elements.libraryTab.setAttribute("aria-selected", String(isLibrary));
  elements.reviewTab.setAttribute("aria-selected", String(!isLibrary));
  elements.libraryTab.tabIndex = isLibrary ? 0 : -1;
  elements.reviewTab.tabIndex = isLibrary ? -1 : 0;
  elements.libraryPanel.hidden = tab !== "library";
  elements.reviewPanel.hidden = tab !== "review";

  if (tab === "review" && !state.currentCard) {
    pickCard();
  }
}

function handleTabKeydown(event) {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
    return;
  }

  event.preventDefault();
  const useReview = event.key === "ArrowRight" || event.key === "End";
  const target = useReview ? elements.reviewTab : elements.libraryTab;
  switchTab(target.dataset.tab);
  target.focus();
}

function renderAll() {
  renderSummary();
  renderLibrary();
  renderReview();
}

function renderSummary() {
  const total = state.words.length;
  const known = state.words.filter((word) => word.reviewStatus === "known").length;
  elements.summary.textContent = total ? `${total} 個單字，${known} 個已標記會了` : "尚未儲存單字";
}

function renderLibrary() {
  const query = elements.searchInput.value.trim().toLowerCase();
  const words = getFilteredWords(query);

  elements.emptyLibrary.hidden = state.words.length !== 0;
  elements.wordList.textContent = "";

  if (!state.words.length) {
    return;
  }

  for (const word of words) {
    elements.wordList.appendChild(createWordRow(word));
  }

  if (query && !words.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "找不到符合搜尋條件的單字。";
    elements.wordList.appendChild(empty);
  }
}

function getFilteredWords(query) {
  const words = [...state.words].sort((a, b) => String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")));
  if (!query) {
    return words;
  }

  return words.filter((word) => {
    const content = [word.text, word.translation, word.partOfSpeech].join(" ").toLowerCase();
    return content.includes(query);
  });
}

function createWordRow(word) {
  const row = document.createElement("article");
  row.className = "word-row";

  const main = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = word.text || word.normalized;
  main.appendChild(title);

  if (word.partOfSpeech) {
    const part = document.createElement("div");
    part.className = "part";
    part.textContent = word.partOfSpeech;
    main.appendChild(part);
  }

  const translation = document.createElement("p");
  translation.textContent = word.translation || "尚無翻譯";
  main.appendChild(translation);

  const meta = document.createElement("small");
  meta.textContent = [
    `查詢 ${Number(word.lookupCount || 0)} 次`,
    `最後 ${formatDate(word.updatedAt)}`,
    reviewLabel(word.reviewStatus)
  ].join(" · ");
  main.appendChild(meta);

  const deleteButton = document.createElement("button");
  deleteButton.className = "danger-button";
  deleteButton.type = "button";
  deleteButton.textContent = "刪除";
  deleteButton.dataset.action = "delete";
  deleteButton.dataset.normalized = word.normalized;

  row.appendChild(main);
  row.appendChild(deleteButton);
  return row;
}

function handleWordListClick(event) {
  const button = event.target.closest("button[data-action='delete']");
  if (!button) {
    return;
  }

  const normalized = button.dataset.normalized;
  sendRuntimeMessage({ type: "DELETE_WORD", normalized }).then((response) => {
    if (response?.ok) {
      state.words = response.words;
      if (state.currentCard?.normalized === normalized) {
        state.currentCard = null;
      }
      renderAll();
    }
  });
}

function renderReview() {
  const hasWords = state.words.length > 0;
  elements.emptyReview.hidden = hasWords;
  elements.flashcard.hidden = !hasWords;

  if (!hasWords) {
    state.currentCard = null;
    return;
  }

  if (!state.currentCard || !state.words.some((word) => word.normalized === state.currentCard.normalized)) {
    pickCard();
    return;
  }

  renderCard();
}

function pickCard() {
  if (!state.words.length) {
    renderReview();
    return;
  }

  const reviewPool = state.words.filter((word) => word.reviewStatus !== "known");
  const pool = reviewPool.length ? reviewPool : state.words;
  let next = pool[Math.floor(Math.random() * pool.length)];

  if (pool.length > 1 && state.currentCard) {
    let attempts = 0;
    while (next.normalized === state.currentCard.normalized && attempts < 8) {
      next = pool[Math.floor(Math.random() * pool.length)];
      attempts += 1;
    }
  }

  state.currentCard = next;
  state.answerVisible = false;
  renderCard();
}

function renderCard() {
  if (!state.currentCard) {
    return;
  }

  const index = state.words.findIndex((word) => word.normalized === state.currentCard.normalized);
  const word = state.words[index] || state.currentCard;
  state.currentCard = word;

  elements.cardStatus.textContent = reviewLabel(word.reviewStatus);
  elements.cardCount.textContent = `${index + 1} / ${state.words.length}`;
  elements.cardWord.textContent = word.text || word.normalized;
  elements.cardHint.textContent = state.answerVisible ? "中文釋義" : "點一下顯示中文釋義";
  elements.cardAnswer.hidden = !state.answerVisible;
  elements.cardPartOfSpeech.textContent = word.partOfSpeech || "";
  elements.cardTranslation.textContent = word.translation || "";
}

function revealAnswer() {
  state.answerVisible = true;
  renderCard();
}

function markReview(status) {
  if (!state.currentCard) {
    return;
  }

  sendRuntimeMessage({
    type: "UPDATE_WORD_REVIEW",
    normalized: state.currentCard.normalized,
    status
  }).then((response) => {
    if (!response?.ok) {
      return;
    }

    state.words = response.words;
    state.currentCard = response.word;
    renderSummary();
    renderLibrary();
    pickCard();
  });
}

function exportJson() {
  const payload = JSON.stringify(state.words, null, 2);
  downloadFile(`gemini-word-bank-${dateStamp()}.json`, "application/json;charset=utf-8", payload);
}

function exportCsv() {
  const headers = [
    "text",
    "translation",
    "partOfSpeech",
    "createdAt",
    "updatedAt",
    "lookupCount",
    "reviewStatus",
    "knownCount",
    "learningCount"
  ];
  const rows = state.words.map((word) => headers.map((key) => csvEscape(word[key])).join(","));
  downloadFile(`gemini-word-bank-${dateStamp()}.csv`, "text/csv;charset=utf-8", `\uFEFF${headers.join(",")}\n${rows.join("\n")}`);
}

function downloadFile(filename, mimeType, content) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function csvEscape(value) {
  const text = value == null ? "" : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function reviewLabel(status) {
  if (status === "known") {
    return "會了";
  }
  if (status === "learning") {
    return "還不熟";
  }
  return "新字";
}

function formatDate(value) {
  if (!value) {
    return "未知";
  }

  return new Intl.DateTimeFormat("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function dateStamp() {
  return new Date().toISOString().slice(0, 10);
}

function sendRuntimeMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (response) => {
      const error = chrome.runtime.lastError;
      if (error) {
        resolve({
          ok: false,
          message: error.message
        });
        return;
      }
      resolve(response);
    });
  });
}
