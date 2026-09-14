import { fail, getEconCalendar } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await getEconCalendar();
    return Response.json(data);
  } catch (err) {
    return fail("econ-calendar", err);
  }
}
