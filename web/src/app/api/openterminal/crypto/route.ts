import { fail, getCrypto } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await getCrypto();
    return Response.json(data);
  } catch (err) {
    return fail("crypto", err);
  }
}
