import { fail, getCalendar } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const symbols = (searchParams.get("symbols") ?? "")
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean)
    .slice(0, 30);
  if (symbols.length === 0) return Response.json({ error: "symbols required" }, { status: 400 });
  try {
    const data = await getCalendar(symbols);
    return Response.json(data);
  } catch (err) {
    return fail("calendar", err);
  }
}
