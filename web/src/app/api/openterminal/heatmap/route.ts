import { fail, getHeatmap } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await getHeatmap();
    return Response.json(data);
  } catch (err) {
    return fail("heatmap", err);
  }
}
