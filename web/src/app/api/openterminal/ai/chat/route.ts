import Anthropic from "@anthropic-ai/sdk";
import type { MessageParam } from "@anthropic-ai/sdk/resources/messages";

// Ported from OpenTerminal's server/src/routes/ai.ts. The original secured
// this route with a local shared-secret (`server/src/auth.ts`) that only made
// sense to guard a second localhost process — dropped here since this is now
// a same-origin Next.js route (see the plan's "Known deliberate deviations").
export const dynamic = "force-dynamic";

// Uses ANTHROPIC_API_KEY from the environment. If it isn't set, the endpoint
// reports the assistant as unavailable (503) — same graceful fallback as the
// original. The user adds this key in Vercel's project settings themselves.
let client: Anthropic | null = null;
function getClient(): Anthropic {
  if (!client) client = new Anthropic();
  return client;
}

const SYSTEM = `You are the AI assistant inside OpenTerminal, a Bloomberg-style financial terminal.
You help the user interpret market data, charts, news, options chains and macro indicators.
Answer concisely and professionally, in the language the user writes in.
When market data is provided in the conversation as JSON context, ground your answer in it.
You are not a licensed financial advisor: never give personalized investment advice or tell the user what to buy or sell.`;

// Best-effort in-memory fixed-window limiter — a deliberate downgrade from the
// original's single-process `rateLimit()` middleware (server/src/rateLimit.ts).
// On Vercel this map is per serverless instance, not global, so it only
// throttles a single warm instance rather than the whole deployment.
const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 10;
const hits = new Map<string, { count: number; resetAt: number }>();

function rateLimited(key: string): number | null {
  const now = Date.now();
  const entry = hits.get(key);
  if (!entry || now > entry.resetAt) {
    hits.set(key, { count: 1, resetAt: now + RATE_WINDOW_MS });
    return null;
  }
  if (entry.count >= RATE_MAX) return Math.ceil((entry.resetAt - now) / 1000);
  entry.count += 1;
  return null;
}

export async function POST(request: Request) {
  const key = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  const retryAfter = rateLimited(key);
  if (retryAfter !== null) {
    return Response.json(
      { error: "rate limit exceeded, try again shortly" },
      { status: 429, headers: { "Retry-After": String(retryAfter) } }
    );
  }

  const body = await request.json().catch(() => null);
  const { messages, context } = body ?? {};
  if (!Array.isArray(messages) || messages.length === 0) {
    return Response.json({ error: "messages array required" }, { status: 400 });
  }

  try {
    const contextBlock: MessageParam[] = context
      ? [{ role: "user", content: `Current terminal context (JSON):\n${JSON.stringify(context)}` }]
      : [];
    const response = await getClient().messages.create({
      model: "claude-sonnet-5",
      max_tokens: 16000,
      thinking: { type: "adaptive" },
      system: SYSTEM,
      messages: [...contextBlock, ...(messages as MessageParam[])],
    });
    if (response.stop_reason === "refusal") {
      return Response.json({ text: "The assistant declined to answer this request." });
    }
    const text = response.content
      .filter((b) => b.type === "text")
      .map((b) => ("text" in b ? b.text : ""))
      .join("");
    return Response.json({ text });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("api_key") || msg.includes("authentication")) {
      return Response.json({ error: "AI assistant unavailable: set ANTHROPIC_API_KEY on the server." }, { status: 503 });
    }
    return Response.json({ error: msg }, { status: 502 });
  }
}
