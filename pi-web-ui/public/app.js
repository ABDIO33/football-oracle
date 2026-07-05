/**
 * Pi Web UI — Frontend Client
 * WebSocket client with full Pi SDK integration
 */

// ─── State ──────────────────────────────────────────────────
const state = {
  ws: null,
  connected: false,
  streaming: false,
  currentMessage: null,   // assistant message being streamed
  currentToolCalls: [],   // tool calls in current turn
  messages: [],
  sessionId: null,
  model: null,
  reconnecting: false,
};

// ─── DOM Elements ────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const els = {
  messages: $("#messages"),
  input: $("#messageInput"),
  sendBtn: $("#sendBtn"),
  thinking: $("#thinkingIndicator"),
  thinkingText: $("#thinkingText"),
  statusBadge: $("#statusBadge"),
  modelBadge: $("#modelBadge"),
  sessionId: $("#sessionId"),
  msgCount: $("#msgCount"),
  headerModel: $("#headerModel"),
  headerSubtitle: $("#headerSubtitle"),
  sidebar: document.querySelector(".sidebar"),
};

// ─── WebSocket Connection ────────────────────────────────────
function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${location.host}`;
  
  state.ws = new WebSocket(wsUrl);
  
  state.ws.onopen = () => {
    console.log("[WS] Connected");
    state.connected = true;
    updateStatus("online");
    if (state.reconnecting) {
      addSystemMessage("🔄 تمت إعادة الاتصال");
      state.reconnecting = false;
    }
  };
  
  state.ws.onclose = () => {
    console.log("[WS] Disconnected");
    state.connected = false;
    state.streaming = false;
    updateStatus("offline");
    hideThinking();
    enableInput();
    
    // Reconnect after 2s
    state.reconnecting = true;
    setTimeout(connect, 2000);
  };
  
  state.ws.onerror = (err) => {
    console.error("[WS] Error:", err);
  };
  
  state.ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleMessage(msg);
    } catch (err) {
      console.error("[WS] Parse error:", err);
    }
  };
}

// ─── Message Handler ────────────────────────────────────────
function handleMessage(msg) {
  switch (msg.type) {
    case "connected":
      state.sessionId = msg.data?.sessionId;
      state.model = msg.data?.model;
      updateInfo();
      break;
      
    case "session_created":
      state.sessionId = msg.sessionId;
      state.model = msg.model;
      state.messages = [];
      els.messages.innerHTML = `<div class="welcome-message">
        <div class="welcome-icon">🤖</div>
        <h2>جلسة جديدة</h2>
        <p>تم إنشاء جلسة جديدة بنجاح</p>
      </div>`;
      updateInfo();
      break;
      
    case "state":
      state.model = msg.data?.model?.id || state.model;
      updateInfo();
      break;
      
    case "pi_event":
      handlePiEvent(msg.event);
      break;
      
    case "error":
      showError(msg.message);
      hideThinking();
      enableInput();
      break;
  }
}

// ─── Pi Event Handler ────────────────────────────────────────
function handlePiEvent(event) {
  switch (event.type) {
    case "agent_start":
      state.streaming = true;
      state.currentToolCalls = [];
      showThinking("Pi يعمل على طلبك...");
      disableInput();
      break;
      
    case "agent_end":
      state.streaming = false;
      hideThinking();
      enableInput();
      state.currentMessage = null;
      break;
      
    case "turn_start":
      break;
      
    case "turn_end":
      state.currentMessage = null;
      state.currentToolCalls = [];
      break;
      
    case "message_start":
      // New assistant message starting
      state.currentMessage = {
        role: "assistant",
        content: "",
        thinking: "",
        toolCalls: [],
        toolResults: [],
      };
      break;
      
    case "message_update": {
      const delta = event.assistantMessageEvent;
      if (!delta) break;
      
      switch (delta.type) {
        case "text_delta":
          if (state.currentMessage) {
            state.currentMessage.content += delta.delta || "";
            updateAssistantMessage();
          }
          break;
          
        case "thinking_delta":
          if (state.currentMessage) {
            state.currentMessage.thinking += delta.delta || "";
            updateThinkingBlock();
          }
          break;
          
        case "toolcall_start": {
          const tc = {
            id: delta.partial?.id || "tc_" + Date.now(),
            name: delta.partial?.name || "tool",
            args: delta.partial?.arguments || {},
            status: "pending",
            result: "",
          };
          state.currentToolCalls.push(tc);
          if (state.currentMessage) {
            state.currentMessage.toolCalls = [...state.currentToolCalls];
          }
          updateToolCalls();
          break;
        }
        
        case "toolcall_delta":
          // Update args of last tool call
          if (state.currentToolCalls.length > 0) {
            const last = state.currentToolCalls[state.currentToolCalls.length - 1];
            try {
              const parsed = JSON.parse(delta.delta || "{}");
              Object.assign(last.args, parsed);
            } catch {
              // Partial JSON, store raw
              last.rawDelta = (last.rawDelta || "") + (delta.delta || "");
            }
          }
          break;
          
        case "toolcall_end":
          if (state.currentToolCalls.length > 0) {
            const last = state.currentToolCalls[state.currentToolCalls.length - 1];
            if (delta.toolCall) {
              last.id = delta.toolCall.id || last.id;
              last.name = delta.toolCall.name || last.name;
              try {
                last.args = typeof delta.toolCall.arguments === 'string' 
                  ? JSON.parse(delta.toolCall.arguments) 
                  : delta.toolCall.arguments || last.args;
              } catch {}
            }
            last.status = "running";
          }
          updateToolCalls();
          break;
          
        case "text_start":
        case "text_end":
        case "thinking_start":
        case "thinking_end":
          break;
          
        case "done":
          updateAssistantMessage(); // Final render
          break;
          
        case "error":
          showError("حدث خطأ في استجابة AI");
          hideThinking();
          enableInput();
          break;
      }
      break;
    }
    
    case "message_end":
      // Finalize the message
      if (state.currentMessage) {
        state.messages.push(state.currentMessage);
        renderAllMessages();
      }
      state.currentMessage = null;
      break;
      
    case "tool_execution_start": {
      const tc = state.currentToolCalls.find(t => t.id === event.toolCallId);
      if (tc) {
        tc.status = "running";
        tc.name = event.toolName;
        tc.args = event.args || tc.args;
        showThinking(`🔧 ${event.toolName}...`);
        updateToolCalls();
      }
      break;
    }
    
    case "tool_execution_update": {
      const tc = state.currentToolCalls.find(t => t.id === event.toolCallId);
      if (tc && event.partialResult) {
        const textContent = event.partialResult.content?.find(c => c.type === "text");
        if (textContent) {
          tc.result = textContent.text;
          updateToolCalls();
        }
      }
      break;
    }
    
    case "tool_execution_end": {
      const tc = state.currentToolCalls.find(t => t.id === event.toolCallId);
      if (tc) {
        tc.status = event.isError ? "error" : "success";
        const textContent = event.result?.content?.find(c => c.type === "text");
        if (textContent) {
          tc.result = textContent.text;
        }
        updateToolCalls();
      }
      break;
    }
    
    case "queue_update":
      if (event.steering?.length > 0) {
        showThinking(`⏳ ${event.steering.length} رسالة في الانتظار...`);
      }
      break;
      
    case "compaction_start":
      showThinking("📦 ضغط السياق...");
      break;
      
    case "compaction_end":
      hideThinking();
      break;
      
    case "extension_error":
      console.error("[Extension Error]", event.error);
      break;
  }
}

// ─── Rendering Functions ─────────────────────────────────────

function renderAllMessages() {
  els.messages.innerHTML = "";
  
  if (state.messages.length === 0) {
    showWelcome();
    return;
  }
  
  for (const msg of state.messages) {
    appendMessageToDOM(msg);
  }
  
  // Add current streaming message if any
  if (state.currentMessage) {
    appendMessageToDOM(state.currentMessage, true);
  }
  
  scrollToBottom();
}

function appendMessageToDOM(msg, isStreaming = false) {
  if (msg.role === "user") {
    addUserMessageDOM(msg.content);
  } else if (msg.role === "assistant" || msg.role === undefined) {
    addAssistantMessageDOM(msg, isStreaming);
  }
}

function addUserMessageDOM(text) {
  const div = document.createElement("div");
  div.className = "message user";
  div.innerHTML = `
    <div class="message-content">${escapeHtml(text)}</div>
    <div class="message-timestamp">${getTime()}</div>
  `;
  removeWelcome();
  els.messages.appendChild(div);
  scrollToBottom();
}

function addAssistantMessageDOM(msg, isStreaming) {
  const div = document.createElement("div");
  div.className = "message assistant";
  div.id = isStreaming ? "streaming-message" : "";
  
  let contentHtml = "";
  
  // Thinking block
  if (msg.thinking) {
    contentHtml += `
      <div class="thinking-block">
        <div class="thinking-label">🤔 Thinking</div>
        <div class="thinking-text" id="thinking-text">${escapeHtml(msg.thinking)}</div>
      </div>`;
  }
  
  // Main content (markdown)
  if (msg.content) {
    contentHtml += `<div class="msg-content" id="msg-content">${renderMarkdown(msg.content)}</div>`;
  }
  
  // Tool calls
  if (msg.toolCalls && msg.toolCalls.length > 0) {
    contentHtml += `<div class="tool-calls" id="tool-calls">`;
    for (const tc of msg.toolCalls) {
      contentHtml += renderToolCall(tc);
    }
    contentHtml += `</div>`;
  }
  
  div.innerHTML = `
    <div class="message-content">${contentHtml}</div>
    <div class="message-timestamp">${isStreaming ? '⌛' : getTime()}</div>
  `;
  
  removeWelcome();
  
  const existing = document.getElementById("streaming-message");
  if (existing) {
    existing.replaceWith(div);
  } else {
    els.messages.appendChild(div);
  }
  
  // Highlight code blocks
  div.querySelectorAll("pre code").forEach((block) => {
    if (window.hljs) {
      hljs.highlightElement(block);
    }
  });
  
  scrollToBottom();
}

function updateAssistantMessage() {
  if (!state.currentMessage) return;
  const existing = document.getElementById("streaming-message");
  if (existing) {
    // Update inline
    const contentEl = existing.querySelector(".msg-content");
    if (contentEl && state.currentMessage.content) {
      contentEl.innerHTML = renderMarkdown(state.currentMessage.content);
      contentEl.querySelectorAll("pre code").forEach((block) => {
        if (window.hljs) hljs.highlightElement(block);
      });
    }
    const thinkEl = existing.querySelector("#thinking-text");
    if (thinkEl && state.currentMessage.thinking) {
      thinkEl.textContent = state.currentMessage.thinking;
    }
  } else if (state.currentMessage.content || state.currentMessage.thinking) {
    addAssistantMessageDOM(state.currentMessage, true);
  }
}

function updateThinkingBlock() {
  updateAssistantMessage();
}

function updateToolCalls() {
  const container = document.getElementById("tool-calls");
  if (!container) return;
  
  container.innerHTML = state.currentToolCalls.map(tc => renderToolCall(tc)).join("");
  
  container.querySelectorAll(".tool-call-header").forEach(header => {
    header.addEventListener("click", () => {
      header.parentElement.classList.toggle("collapsed");
    });
  });
}

function renderToolCall(tc) {
  const statusClass = tc.status === "error" ? "error" : tc.status === "success" ? "success" : "pending";
  const icon = tc.status === "running" ? "⏳" : tc.status === "success" ? "✅" : tc.status === "error" ? "❌" : "⚡";
  
  let body = "";
  if (tc.args && Object.keys(tc.args).length > 0) {
    body += `<div class="tool-call-body">${escapeHtml(JSON.stringify(tc.args, null, 2))}</div>`;
  }
  if (tc.result) {
    body += `<div class="tool-call-body">${escapeHtml(tc.result.substring(0, 500))}</div>`;
  }
  
  return `
    <div class="tool-call ${statusClass} collapsed">
      <div class="tool-call-header">
        <span class="tool-chevron">▼</span>
        ${icon} ${tc.name}
        <span style="margin-right:auto;font-size:0.7rem;opacity:0.6">${tc.id.substring(0, 8)}</span>
      </div>
      ${body}
    </div>`;
}

function renderMarkdown(text) {
  if (!text) return "";
  try {
    // Configure marked for safety
    const renderer = new marked.Renderer();
    const html = marked.parse(text, {
      breaks: true,
      gfm: true,
      renderer,
    });
    return html;
  } catch (e) {
    return escapeHtml(text);
  }
}

// ─── UI Helpers ──────────────────────────────────────────────

function addUserMessage(text) {
  addUserMessageDOM(text);
  state.messages.push({ role: "user", content: text });
}

function addSystemMessage(text) {
  const div = document.createElement("div");
  div.className = "message system";
  div.innerHTML = `<div class="message-content">${text}</div>`;
  els.messages.appendChild(div);
  scrollToBottom();
}

function showWelcome() {
  els.messages.innerHTML = `<div class="welcome-message">
    <div class="welcome-icon">🤖</div>
    <h2>مرحباً بك في Pi Web UI!</h2>
    <p>واجهة رسومية كاملة لـ <strong>Pi Coding Agent</strong></p>
    <p class="welcome-hint">جميع مزايا pi متوفرة — tools, skills, extensions — بدون فقدان أي شيء</p>
    <div class="welcome-cmds">
      <code>ask any question</code>
      <code>!command</code>
      <code>/command</code>
      <code>@file</code>
    </div>
  </div>`;
}

function removeWelcome() {
  const welcome = els.messages.querySelector(".welcome-message");
  if (welcome) welcome.remove();
}

function showThinking(text) {
  els.thinking.classList.add("active");
  els.thinkingText.textContent = text || "Pi هو يفكر...";
}

function hideThinking() {
  els.thinking.classList.remove("active");
}

function updateStatus(status) {
  els.statusBadge.innerHTML = `<span class="status-dot ${status}"></span>${status === "online" ? "متصل" : status === "thinking" ? "يعمل" : "غير متصل"}`;
}

function updateInfo() {
  els.modelBadge.textContent = state.model || "غير معروف";
  els.sessionId.textContent = state.sessionId ? state.sessionId.substring(0, 12) + "..." : "—";
  els.msgCount.textContent = state.messages.length;
  els.headerModel.textContent = state.model || "Pi Web UI";
}

function scrollToBottom() {
  setTimeout(() => {
    els.messages.scrollTop = els.messages.scrollHeight;
  }, 50);
}

function getTime() {
  return new Date().toLocaleTimeString("ar-SA", { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function showError(msg) {
  const toast = document.createElement("div");
  toast.className = "error-toast";
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function disableInput() {
  els.input.disabled = true;
  els.sendBtn.disabled = true;
  els.input.placeholder = "في انتظار رد Pi...";
}

function enableInput() {
  els.input.disabled = false;
  els.sendBtn.disabled = false;
  els.input.placeholder = "اكتب رسالتك هنا... (! لأوامر bash، / لأوامر pi)";
  els.input.focus();
}

// ─── Actions ─────────────────────────────────────────────────

function sendMessage() {
  const text = els.input.value.trim();
  if (!text || !state.ws || state.streaming) return;
  
  els.input.value = "";
  els.input.style.height = "auto";
  
  addUserMessage(text);
  state.streaming = true;
  showThinking("جاري الإرسال...");
  disableInput();
  
  state.ws.send(JSON.stringify({ type: "prompt", message: text }));
}

function sendMsg(text) {
  els.input.value = text;
  sendMessage();
}

function abort() {
  if (state.ws && state.streaming) {
    state.ws.send(JSON.stringify({ type: "abort" }));
    hideThinking();
    enableInput();
    addSystemMessage("⛔ تم إيقاف الاستجابة");
  }
}

function newSession() {
  if (state.ws) {
    state.ws.send(JSON.stringify({ type: "new_session" }));
    state.messages = [];
    renderAllMessages();
    addSystemMessage("📄 تم إنشاء جلسة جديدة");
  }
}

function getState() {
  if (state.ws) {
    state.ws.send(JSON.stringify({ type: "get_state" }));
  }
}

function toggleSidebar() {
  document.querySelector(".sidebar").classList.toggle("open");
}

function handleFiles(files) {
  if (files.length > 0) {
    addSystemMessage(`📎 تم رفع ${files.length} ملف (قريباً)`);
  }
}

// ─── Input auto-resize ───────────────────────────────────────
els.input.addEventListener("input", () => {
  els.input.style.height = "auto";
  els.input.style.height = Math.min(els.input.scrollHeight, 200) + "px";
});

els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// ─── Init ────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  console.log("Pi Web UI — Starting...");
  connect();
  els.input.focus();
});
