import { fail, getScreener } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const num = (v: string | null) => (v === null ? undefined : Number(v));
  try {
    const data = await getScreener({
      sector: searchParams.get("sector") ?? undefined,
      marketCapMin: num(searchParams.get("marketCapMin")),
      changeMin: num(searchParams.get("changeMin")),
      changeMax: num(searchParams.get("changeMax")),
      volumeMin: num(searchParams.get("volumeMin")),
      sort: searchParams.get("sort") ?? "marketCap",
      dir: searchParams.get("dir") === "asc" ? "asc" : "desc",
    });
    return Response.json(data);
  } catch (err) {
    return fail("screener", err);
  }
}
