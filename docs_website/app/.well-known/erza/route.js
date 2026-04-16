import { buildDocsErzaSource, normalizeDocsErzaPath } from "@/lib/readme-docs";

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const requestedPath = normalizeDocsErzaPath(searchParams.get("path") || "/");
  if (!requestedPath) {
    return new Response("invalid erza page path\n", {
      status: 400,
      headers: { "content-type": "text/plain; charset=utf-8" }
    });
  }

  const source = buildDocsErzaSource(requestedPath);
  if (!source) {
    return new Response("erza page not found\n", {
      status: 404,
      headers: { "content-type": "text/plain; charset=utf-8" }
    });
  }

  return new Response(source, {
    headers: {
      "cache-control": "public, max-age=0, must-revalidate",
      "content-type": "application/erza; charset=utf-8",
      vary: "accept"
    }
  });
}
