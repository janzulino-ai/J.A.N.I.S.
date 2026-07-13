/**
 * JANIS WhatsApp Bridge — riceve messaggi WA, inoltra a JANIS, invia risposte.
 *
 * Env:
 *   JANIS_HUB_URL     http://127.0.0.1:8001
 *   WHATSAPP_BRIDGE_TOKEN  stesso valore in .env JANIS
 *   WHATSAPP_BRIDGE_PORT   default 8787
 */
import express from "express";
import qrcode from "qrcode-terminal";
import whatsapp from "whatsapp-web.js";

const { Client, LocalAuth } = whatsapp;

const HUB = (process.env.JANIS_HUB_URL || "http://127.0.0.1:8001").replace(/\/$/, "");
const TOKEN = process.env.WHATSAPP_BRIDGE_TOKEN || "";
const PORT = parseInt(process.env.WHATSAPP_BRIDGE_PORT || "8787", 10);
const BOT_NAME = (process.env.JANIS_WA_NAME || "janis").toLowerCase();

const client = new Client({ authStrategy: new LocalAuth({ dataPath: "./.wwebjs_auth" }) });

async function forwardToJanis(payload) {
  const headers = { "Content-Type": "application/json" };
  if (TOKEN) headers.Authorization = `Bearer ${TOKEN}`;
  const res = await fetch(`${HUB}/api/channels/whatsapp/inbound`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    console.error("JANIS inbound HTTP", res.status, await res.text());
    return null;
  }
  const data = await res.json();
  return data.reply || null;
}

client.on("qr", (qr) => {
  console.log("Scansiona QR con WhatsApp:");
  qrcode.generate(qr, { small: true });
});

client.on("ready", () => console.log("WhatsApp bridge pronto"));

client.on("message", async (msg) => {
  try {
    if (msg.fromMe) return;
    const chat = await msg.getChat();
    const body = (msg.body || "").trim();
    if (!body) return;
    const isGroup = chat.isGroup;
    let mentioned = !isGroup;
    if (isGroup) {
      const mentions = await msg.getMentions();
      mentioned = mentions.some((c) => c.isMe) || body.toLowerCase().includes(BOT_NAME);
    }
    const payload = {
      from_id: msg.from,
      chat_id: msg.from,
      text: body,
      is_group: isGroup,
      mentioned,
      sender_name: (await msg.getContact())?.pushname || msg.from,
    };
    const reply = await forwardToJanis(payload);
    if (reply) await msg.reply(reply.slice(0, 4000));
  } catch (e) {
    console.error("message handler", e);
  }
});

const app = express();
app.use(express.json());

app.get("/health", (_req, res) => res.json({ ok: true, service: "janis-whatsapp-bridge" }));

app.post("/send", async (req, res) => {
  if (TOKEN) {
    const auth = req.headers.authorization || "";
    if (auth !== `Bearer ${TOKEN}`) return res.status(403).json({ error: "forbidden" });
  }
  const to = req.body?.to;
  const message = req.body?.message;
  if (!to || !message) return res.status(400).json({ error: "to and message required" });
  try {
    const chatId = to.includes("@") ? to : `${to}@c.us`;
    await client.sendMessage(chatId, String(message).slice(0, 4000));
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

app.listen(PORT, () => console.log(`Bridge HTTP :${PORT} → JANIS ${HUB}`));
client.initialize();
