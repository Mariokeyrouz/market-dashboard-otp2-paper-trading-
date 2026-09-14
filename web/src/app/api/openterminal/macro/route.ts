import { fail, getMacro } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await getMacro();
    return Response.json(data);
  } catch (err) {
    return fail("macro", err);
  }
}
