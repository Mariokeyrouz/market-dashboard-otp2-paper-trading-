import { fail, getRecap } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await getRecap();
    return Response.json(data);
  } catch (err) {
    return fail("recap", err);
  }
}
