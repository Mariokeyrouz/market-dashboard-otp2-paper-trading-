import { fail, getOptions } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ symbol: string }> }) {
  const { symbol: rawSymbol } = await params;
  const symbol = rawSymbol.toUpperCase();
  const { searchParams } = new URL(request.url);
  const expiry = searchParams.get("expiry") ?? undefined;
  try {
    const data = await getOptions(symbol, expiry);
    return Response.json(data);
  } catch (err) {
    return fail("options", err);
  }
}
