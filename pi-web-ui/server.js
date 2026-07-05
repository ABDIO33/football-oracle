/**
 * Pi Web UI Server
 * Uses Pi SDK directly — ALL features preserved, zero losses
 * WebSocket streaming + beautiful web frontend
 */
import express from "express";
import { createServer } from "http";
import { WebSocketServer } from "ws";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

import {
  AuthStorage,
  createAgentSession,
  ModelRegistry,
  SessionManager,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORT = 3456;

// ─── Express Setup ────────────────────────────────────────────
const app = express();
app.use(express.json());
app.use(express.static(join(__dirname, "public")));

const server = createServer(app);

// ─── WebSocket Server ──────────────────────────────────────────
const wss = new WebSocketServer({ server });

// ─── Pi Session Manager ────────────────────────────────────────
let activeSession = null;
let activeWs = null;

async function broadcast(event) {
  if (activeWs?.readyState === 1) {
    try {
      activeWs.send(JSON.stringify(event));
    } catch (e) {
      console.error("[WS] send error:", e.message);
    }
  }
}

async function createPiSession() {
  try {
    const authStorage = AuthStorage.create();
    const modelRegistry = ModelRegistry.create(authStorage);

    const settingsManager = SettingsManager.create(
      process.cwd(),
      process.env.HOME + "/.pi/agent"
    );

    // Get all available models
    const available = await modelRegistry.getAvailable();
    console.log(`[Pi] ${available.length} models available`);

    const { session } = await createAgentSession({
      sessionManager: SessionManager.inMemory(process.cwd()),
      authStorage,
      modelRegistry,
      settingsManager,
    });

    // Subscribe to ALL events and broadcast via WebSocket
    session.subscribe((event) => {
      broadcast({ type: "pi_event", event });
    });

    console.log(`[Pi] Session created: ${session.sessionId}`);
    console.log(`[Pi] Model: ${session.model?.id || "default"}`);
    return session;
  } catch (err) {
    console.error("[Pi] Failed to create session:", err.message);
    throw err;
  }
}

// ─── WebSocket Connection Handler ──────────────────────────────
wss.on("connection", async (ws) => {
  console.log("[WS] Client connected");
  activeWs = ws;

  // Send session info
  ws.send(JSON.stringify({
    type: "connected",
    data: {
      model: activeSession?.model?.id || "loading...",
      sessionId: activeSession?.sessionId || "none",
    }
  }));

  ws.on("message", async (data) => {
    try {
      const msg = JSON.parse(data.toString());

      switch (msg.type) {
        case "prompt":
          if (!activeSession) {
            ws.send(JSON.stringify({
              type: "error",
              message: "Session not ready. Please wait..."
            }));
            return;
          }
          try {
            await activeSession.prompt(msg.message, {
              streamingBehavior: msg.streamingBehavior || undefined,
            });
          } catch (err) {
            ws.send(JSON.stringify({
              type: "error",
              message: err.message
            }));
          }
          break;

        case "steer":
          if (activeSession) {
            await activeSession.steer(msg.message);
          }
          break;

        case "followUp":
          if (activeSession) {
            await activeSession.followUp(msg.message);
          }
          break;

        case "abort":
          if (activeSession) {
            await activeSession.abort();
          }
          break;

        case "new_session":
          if (activeSession) {
            activeSession.dispose();
          }
          activeSession = await createPiSession();
          ws.send(JSON.stringify({
            type: "session_created",
            sessionId: activeSession.sessionId,
            model: activeSession.model?.id
          }));
          break;

        case "get_state":
          if (activeSession) {
            ws.send(JSON.stringify({
              type: "state",
              data: {
                model: activeSession.model,
                thinkingLevel: activeSession.thinkingLevel,
                isStreaming: activeSession.isStreaming,
                messages: activeSession.messages.length,
                sessionId: activeSession.sessionId,
              }
            }));
          }
          break;

        case "get_messages":
          if (activeSession) {
            ws.send(JSON.stringify({
              type: "messages",
              messages: activeSession.messages
            }));
          }
          break;

        default:
          ws.send(JSON.stringify({
            type: "error",
            message: `Unknown command: ${msg.type}`
          }));
      }
    } catch (err) {
      console.error("[WS] message error:", err);
      ws.send(JSON.stringify({ type: "error", message: err.message }));
    }
  });

  ws.on("close", () => {
    console.log("[WS] Client disconnected");
    activeWs = null;
  });
});

// ─── API Routes ───────────────────────────────────────────────

// Health / status
app.get("/api/status", (req, res) => {
  res.json({
    status: "running",
    session: activeSession ? {
      id: activeSession.sessionId,
      model: activeSession.model?.id,
      messages: activeSession.messages.length,
      isStreaming: activeSession.isStreaming,
    } : null,
  });
});

// Get available models
app.get("/api/models", async (req, res) => {
  try {
    const authStorage = AuthStorage.create();
    const modelRegistry = ModelRegistry.create(authStorage);
    const available = await modelRegistry.getAvailable();
    res.json({ models: available.map(m => ({ id: m.id, name: m.name, provider: m.provider })) });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Start ────────────────────────────────────────────────────
async function start() {
  try {
    activeSession = await createPiSession();

    server.listen(PORT, () => {
      console.log("\n" + "=".repeat(60));
      console.log("   🎯 Pi Web UI — Chat Interface");
      console.log(`   🌐 http://localhost:${PORT}`);
      console.log("=".repeat(60) + "\n");
    });
  } catch (err) {
    console.error("[FATAL] Could not start:", err.message);
    process.exit(1);
  }
}

start();

// Graceful shutdown
process.on("SIGINT", async () => {
  console.log("\nShutting down...");
  if (activeSession) activeSession.dispose();
  process.exit(0);
});
