import { buildLlmsIndex } from "@/lib/readme-docs";

export const dynamic = "force-static";

export async function GET(request) {
  const origin = new URL(request.url).origin;
  return new Response(buildLlmsIndex(origin), {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "public, max-age=0, must-revalidate"
    }
  });
}
