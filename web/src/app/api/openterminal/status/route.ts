import { allStats } from "@/lib/openterminal/providers/registry";

// Equivalent of the original server's `GET /api/status` (server/src/index.ts),
// reusing the same provider stats registry. There's no separate Express
// process here, so "ok" is always true — this just reports data-provider
// health and whether an Anthropic API key is configured for the AI widget.
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(
    {
      ok: true,
      time: new Date().toISOString(),
      providers: allStats(),
      ai: Boolean(process.env.ANTHROPIC_API_KEY),
    },
    { headers: { "Cache-Control": "no-store" } }
  );
}
