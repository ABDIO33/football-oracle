// Load plugin first
require("C:/Users/zake.exe/.config/opencode/plugins/agentrouter-auth.js");

const { createOpenAICompatible } = require("@ai-sdk/openai-compatible");

// @ai-sdk/openai-compatible needs ai package too
let generateText;
try {
  ({ generateText } = require("ai"));
} catch(e) {
  console.log("ai package not found, trying direct...");
}

async function test() {
  const provider = createOpenAICompatible({
    name: "agentrouter",
    baseURL: "https://agentrouter.org/v1",
    apiKey: "sk-j22yAVjq7BcKpL4bgwRpqTGMcCWB74gE8ZEiGA8zyDN3AIVw",
  });

  const model = provider.chatModel("claude-opus-4-6");

  try {
    if (generateText) {
      const result = await generateText({
        model,
        messages: [{ role: "user", content: "Say OK in 2 words" }],
      });
      console.log("SUCCESS:", result.text);
    } else {
      // Try low-level API
      const result = await model.doGenerate({
        inputFormat: "messages",
        mode: { type: "regular" },
        prompt: [{ role: "user", content: [{ type: "text", text: "Say OK" }] }],
      });
      console.log("Result:", JSON.stringify(result).substring(0, 500));
    }
  } catch (e) {
    console.log("ERROR:", e.message);
  }
}

test().catch(console.error);
