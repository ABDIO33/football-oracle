/**
 * Pi Web UI v3 — أنا الحقيقي في الواجهة + ذاكرة دائمة + xhigh
 * 
 * Features:
 * - Pi SDK → ALL tools, skills, extensions preserved
 * - AGENTS.md → full project context loaded
 * - Session persistence → conversation survives page refresh
 * - thinkingLevel: xhigh → أقصى ذكاء
 * - RESTORE previous messages on reconnect
 */

import express from "express";
import { createServer } from "http";
import { WebSocketServer } from "ws";
import path from "path";
import { fileURLToPath } from "url";
import fs from "fs";

import {
  AuthStorage,
  createAgentSession,
  ModelRegistry,
  SessionManager,
  DefaultResourceLoader,
} from "@earendil-works/pi-coding-agent";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = 3456;
const PUBLIC = path.join(__dirname, "public");

// ─── Session Store (persistence) ────────────────────────────
const SESSION_DIR = path.join(__dirname, ".pi", "sessions");

// ─── Express Setup ────────────────────────────────────────────
const app = express();
app.use(express.json());
app.use(express.static(PUBLIC));

const server = createServer(app);
const wss = new WebSocketServer({ server });

function send(ws, data) {
  if (ws?.readyState === 1) {
    try { ws.send(JSON.stringify(data)); } catch (_) {}
  }
}

// ─── Extract readable messages from session ─────────────────
function extractText(content) {
  if (!content) return "";
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .filter(c => c.type === "text")
      .map(c => c.text || "")
      .join("\n");
  }
  return "";
}

function extractMessages(session) {
  return (session.messages || [])
    .filter(m => m.role === "user" || m.role === "assistant")
    .map(m => ({
      role: m.role,
      content: extractText(m.content),
    }));
}

// ─── Create or Resume Session ────────────────────────────────
async function getOrCreateSession(sessionFile) {
  const authStorage = AuthStorage.create();
  const modelRegistry = ModelRegistry.create(authStorage);

  const resourceLoader = new DefaultResourceLoader({
    cwd: __dirname,
    agentDir: path.join(process.env.HOME || "~", ".pi", "agent"),
  });
  await resourceLoader.reload();

  let sessionManager;

  if (sessionFile && fs.existsSync(sessionFile)) {
    sessionManager = SessionManager.open(sessionFile);
  } else {
    sessionManager = SessionManager.create(__dirname);
  }

  const { session } = await createAgentSession({
    cwd: __dirname,
    sessionManager,
    authStorage,
    modelRegistry,
    resourceLoader,
    thinkingLevel: "high", // ← ذكاء عالي + عرض التفكير فوراً
  });

  return session;
}

// ─── WebSocket Handler ────────────────────────────────────────
wss.on("connection", async (ws) => {
  console.log("[WS] Client connected");

  let session;
  let sessionFile = null;

  try {
    session = await getOrCreateSession();
    sessionFile = session.sessionFile;

    console.log(`[Pi] Session: ${session.sessionId}`);
    console.log(`[Pi] Model: ${session.model?.id}`);
    console.log(`[Pi] Thinking: xhigh (max)`);
  } catch (err) {
    console.error("[WS] Session error:", err);
    send(ws, { type: "error", message: "Agent init failed: " + err.message });
    return;
  }

  // Send session info + all saved messages
  const savedMessages = extractMessages(session);
  send(ws, {
    type: "connected",
    model: session.model?.id || "unknown",
    sessionId: session.sessionId,
    sessionFile,
    messages: savedMessages,
  });

  const unsubscribe = session.subscribe((event) => {
    send(ws, { type: "pi_event", event });
  });

  ws.on("message", async (raw) => {
    let msg;
    try { msg = JSON.parse(raw.toString()); } catch { return; }

    try {
      if (msg.type === "prompt") {
        if (!msg.message?.trim()) return;
        session.prompt(msg.message).then(() => {
          console.log("[WS] ✓ prompt done");
        }).catch(err => {
          console.error("[WS] Prompt error:", err);
          send(ws, { type: "error", message: err.message });
        });
      } else if (msg.type === "abort") {
        await session.abort();
      } else if (msg.type === "resume") {
        const resumeFile = msg.sessionFile;
        if (resumeFile && fs.existsSync(resumeFile)) {
          try {
            unsubscribe();
            session.dispose();

            session = await getOrCreateSession(resumeFile);
            sessionFile = session.sessionFile;

            // Re-subscribe
            session.subscribe((event) => {
              send(ws, { type: "pi_event", event });
            });

            const restoredMessages = extractMessages(session);
            send(ws, {
              type: "resumed",
              sessionId: session.sessionId,
              sessionFile,
              messages: restoredMessages,
            });
            console.log(`[Pi] Resumed: ${resumeFile} (${restoredMessages.length} msgs)`);
          } catch (err) {
            send(ws, { type: "error", message: "Resume failed: " + err.message });
          }
        } else {
          send(ws, { type: "error", message: "Session file not found" });
        }
      }
    } catch (err) {
      console.error("[WS] Error:", err);
      send(ws, { type: "error", message: err.message });
    }
  });

  ws.on("close", () => {
    console.log("[WS] Client disconnected");
    unsubscribe();
    session.dispose();
  });
});

// ─── API ─────────────────────────────────────────────────────
app.get("/api/status", (_req, res) => {
  res.json({
    status: "running",
    clients: wss.clients.size,
  });
});

// ─── Start ────────────────────────────────────────────────────
console.log("\n" + "=".repeat(60));
console.log("   🏆 Pi Web UI v3 — أنا الحقيقي في الواجهة");
console.log(`   🌐 http://localhost:${PORT}`);
console.log("   🧠 ذاكرة دائمة + عرض المحادثات السابقة");
console.log("   ⚡ Thinking: high (ذكاء + عرض التفكير فوراً)");
console.log("=".repeat(60) + "\n");

server.listen(PORT);
