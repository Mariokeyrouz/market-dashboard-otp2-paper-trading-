import { fail, getSearch } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const q = (searchParams.get("q") ?? "").trim();
  if (!q) return Response.json([]);
  try {
    const data = await getSearch(q);
    return Response.json(data);
  } catch (err) {
    return fail("search", err);
  }
}
