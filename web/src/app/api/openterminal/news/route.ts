import { fail, getNews } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const symbolParam = searchParams.get("symbol");
  const symbol = symbolParam ? symbolParam.toUpperCase() : null;
  try {
    const data = await getNews(symbol);
    return Response.json(data);
  } catch (err) {
    return fail("news", err);
  }
}
