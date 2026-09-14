import { fail, getCryptoGlobal } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await getCryptoGlobal();
    return Response.json(data);
  } catch (err) {
    return fail("crypto/global", err);
  }
}
