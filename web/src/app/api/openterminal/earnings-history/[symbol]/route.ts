import { fail, getEarningsHistory } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{ symbol: string }> }) {
  const { symbol: rawSymbol } = await params;
  const symbol = rawSymbol.toUpperCase();
  try {
    const data = await getEarningsHistory(symbol);
    return Response.json(data);
  } catch (err) {
    return fail("earnings-history", err);
  }
}
