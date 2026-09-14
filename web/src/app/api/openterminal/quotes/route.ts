import { fail, getQuotes } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const symbols = (searchParams.get("symbols") ?? "")
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean)
    .slice(0, 150);
  if (symbols.length === 0) return Response.json({ error: "symbols required" }, { status: 400 });
  try {
    const data = await getQuotes(symbols);
    if (data.length === 0) throw new Error("no quotes from any provider");
    return Response.json(data);
  } catch (err) {
    return fail("quotes", err);
  }
}
