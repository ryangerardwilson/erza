import { readCanonicalReadme } from "@/lib/readme-docs";

export async function GET() {
  return new Response(readCanonicalReadme(), {
    headers: {
      "cache-control": "public, max-age=0, must-revalidate",
      "content-disposition": "inline; filename=\"README.md\"",
      "content-type": "text/markdown; charset=utf-8"
    }
  });
}
