import { fail, getHistory } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ symbol: string }> }) {
  const { symbol: rawSymbol } = await params;
  const symbol = rawSymbol.toUpperCase();
  const { searchParams } = new URL(request.url);
  const rangeKey = searchParams.get("range") ?? "6M";
  try {
    const data = await getHistory(symbol, rangeKey);
    return Response.json(data);
  } catch (err) {
    return fail("history", err);
  }
}
