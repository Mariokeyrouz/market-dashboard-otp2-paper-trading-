import { fail, getCryptoOrderbook } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  try {
    const data = await getCryptoOrderbook(symbol);
    return Response.json(data);
  } catch (err) {
    return fail("crypto/orderbook", err);
  }
}
