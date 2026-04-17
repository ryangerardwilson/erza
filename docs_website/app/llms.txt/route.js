import { buildLlmsIndex } from "@/lib/readme-docs";

export const dynamic = "force-static";

export async function GET() {
  return new Response(buildLlmsIndex(), {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "public, max-age=0, must-revalidate"
    }
  });
}
