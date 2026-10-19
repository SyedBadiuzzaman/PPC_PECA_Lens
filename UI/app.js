(() => {
  "use strict";

  const form = document.querySelector("#question-form");
  if (!form) {
    return;
  }

  const input = document.querySelector("#question-input");
  const sendButton = document.querySelector("#send-button");
  const newSessionButton = document.querySelector("#new-session");
  const sessionState = document.querySelector("#session-state");
  const serviceBanner = document.querySelector("#service-banner");
  const serviceMessage = document.querySelector("#service-message");
  const retryHealthButton = document.querySelector("#retry-health");
  const characterCount = document.querySelector("#character-count");
  const emptyState = document.querySelector("#empty-state");
  const transcript = document.querySelector("#transcript");
  const promptOptions = [...document.querySelectorAll(".prompt-option")];

  let serviceReady = false;
  let requestInFlight = false;
  let sessionStarted = false;

  const setBanner = (message, state) => {
    serviceMessage.textContent = message;
    serviceBanner.classList.remove("is-ready", "is-error");
    if (state === "ready") {
      serviceBanner.classList.add("is-ready");
    }
    if (state === "error") {
      serviceBanner.classList.add("is-error");
    }
  };

  const updateControls = () => {
    const canAsk = serviceReady && !requestInFlight;
    input.disabled = !canAsk;
    sendButton.disabled = !canAsk || input.value.trim().length === 0;
    promptOptions.forEach((button) => {
      button.disabled = !canAsk;
    });
    newSessionButton.disabled = !sessionStarted || requestInFlight;
    form.setAttribute("aria-busy", String(requestInFlight));
  };

  const requestJson = async (url, options, timeoutMilliseconds) => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMilliseconds);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      let payload = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
      if (!response.ok) {
        const error = new Error(
          payload && typeof payload.detail === "string"
            ? payload.detail
            : "The service could not complete the request."
        );
        error.status = response.status;
        throw error;
      }
      return payload;
    } finally {
      window.clearTimeout(timeoutId);
    }
  };

  const checkHealth = async () => {
    serviceReady = false;
    retryHealthButton.hidden = true;
    setBanner("Checking local service readiness...", "checking");
    updateControls();

    try {
      const health = await requestJson(
        "/health",
        { method: "GET", headers: { Accept: "application/json" }, cache: "no-store" },
        7000
      );
      serviceReady = Boolean(health && health.status === "ready");
      if (serviceReady) {
        setBanner("Local sources and configured models are ready.", "ready");
      } else {
        setBanner("The local service is not ready. Complete configuration and ingestion, then check again.", "error");
        retryHealthButton.hidden = false;
      }
    } catch (error) {
      const message = error.name === "AbortError"
        ? "The readiness check timed out."
        : "The local backend could not be reached.";
      setBanner(message, "error");
      retryHealthButton.hidden = false;
    }
    updateControls();
  };

  const createElement = (tagName, className, text) => {
    const element = document.createElement(tagName);
    if (className) {
      element.className = className;
    }
    if (typeof text === "string") {
      element.textContent = text;
    }
    return element;
  };

  const appendUserMessage = (question) => {
    const article = createElement("article", "message message-user");
    article.setAttribute("aria-label", "Your question");
    article.append(createElement("p", "", question));
    transcript.append(article);
  };

  const appendLoadingMessage = () => {
    const article = createElement("article", "message message-assistant loading-message");
    article.setAttribute("aria-label", "Preparing a source-grounded response");
    article.setAttribute("role", "status");
    article.append(createElement("p", "message-label", "Reviewing retrieved sources"));
    for (let index = 0; index < 3; index += 1) {
      article.append(createElement("div", "loading-line"));
    }
    transcript.append(article);
    return article;
  };

  const formatStatus = (value) => {
    if (typeof value !== "string" || value.length === 0) {
      return "Response";
    }
    const words = value.replaceAll("_", " ");
    return words.charAt(0).toUpperCase() + words.slice(1);
  };

  const appendAnswerText = (container, answer) => {
    const paragraphs = String(answer || "No answer was returned.")
      .split(/\n\s*\n/)
      .filter((paragraph) => paragraph.trim().length > 0);
    paragraphs.forEach((paragraph) => {
      container.append(createElement("p", "", paragraph.trim()));
    });
  };

  const appendWarnings = (article, warnings) => {
    if (!Array.isArray(warnings) || warnings.length === 0) {
      return;
    }
    const list = createElement("ul", "warning-list");
    warnings.forEach((warning) => {
      list.append(createElement("li", "", String(warning)));
    });
    article.append(list);
  };

  const appendSources = (article, sources) => {
    if (!Array.isArray(sources) || sources.length === 0) {
      return;
    }

    const details = createElement("details", "source-disclosure");
    details.append(createElement("summary", "", `Verified sources (${sources.length})`));
    const list = createElement("div", "source-list");

    sources.forEach((source) => {
      const item = createElement("article", "source-item");
      const law = typeof source.law === "string" ? source.law.toUpperCase() : "Source";
      const page = Number.isFinite(source.page) ? source.page : "Unknown";
      item.append(createElement("h3", "", `${law} | Physical page ${page}`));
      item.append(createElement("p", "source-meta", `${String(source.source || "Unknown file")} | Chunk ${String(source.chunk_id || "Unknown")}`));
      item.append(createElement("blockquote", "", String(source.quote || "No quotation returned.")));
      list.append(item);
    });

    details.append(list);
    article.append(details);
  };

  const appendAssistantMessage = (response) => {
    const article = createElement("article", "message message-assistant");
    article.setAttribute("aria-label", "PPC-PECA Lens response");

    const heading = createElement("header", "message-heading");
    heading.append(createElement("span", "message-label", "PPC-PECA Lens"));
    if (response.law) {
      heading.append(createElement("span", "result-badge", String(response.law).toUpperCase()));
    }
    heading.append(createElement("span", "result-badge", formatStatus(response.status)));
    article.append(heading);

    const answer = createElement("div", "answer-copy");
    appendAnswerText(answer, response.answer);
    article.append(answer);
    appendWarnings(article, response.warnings);
    appendSources(article, response.sources);
    transcript.append(article);
  };

  const appendErrorMessage = (message) => {
    const section = createElement("section", "message inline-error");
    section.setAttribute("role", "alert");
    section.append(createElement("h2", "", "The question could not be completed"));
    section.append(createElement("p", "", message));
    transcript.append(section);
  };

  const scrollToLatest = () => {
    const latest = transcript.lastElementChild;
    if (latest) {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      latest.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
    }
  };

  const resizeInput = () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
    input.style.overflowY = input.scrollHeight > 180 ? "auto" : "hidden";
  };

  const updateCharacterCount = () => {
    characterCount.textContent = `${input.value.length} / 4000`;
    updateControls();
  };

  const startSession = () => {
    if (sessionStarted) {
      return;
    }
    sessionStarted = true;
    emptyState.hidden = true;
    sessionState.textContent = "Active private session";
    updateControls();
  };

  const clearSession = () => {
    transcript.replaceChildren();
    input.value = "";
    resizeInput();
    updateCharacterCount();
    sessionStarted = false;
    emptyState.hidden = false;
    sessionState.textContent = "No active session";
    updateControls();
    input.focus();
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!serviceReady || requestInFlight || question.length === 0) {
      input.focus();
      return;
    }

    startSession();
    appendUserMessage(question);
    input.value = "";
    resizeInput();
    updateCharacterCount();
    requestInFlight = true;
    updateControls();
    const loadingMessage = appendLoadingMessage();
    scrollToLatest();

    try {
      const response = await requestJson(
        "/query",
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ question })
        },
        20000
      );
      loadingMessage.remove();
      appendAssistantMessage(response || {});
    } catch (error) {
      loadingMessage.remove();
      const message = error.name === "AbortError"
        ? "The request exceeded the browser deadline. Try again when the service is available."
        : error.message || "The local service could not complete this question.";
      appendErrorMessage(message);
    } finally {
      requestInFlight = false;
      updateControls();
      scrollToLatest();
      input.focus();
    }
  });

  input.addEventListener("input", () => {
    resizeInput();
    updateCharacterCount();
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  promptOptions.forEach((button) => {
    button.addEventListener("click", () => {
      input.value = button.textContent.trim();
      resizeInput();
      updateCharacterCount();
      input.focus();
    });
  });

  retryHealthButton.addEventListener("click", checkHealth);
  newSessionButton.addEventListener("click", clearSession);

  updateCharacterCount();
  checkHealth();
})();
