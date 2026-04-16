import { readCanonicalSkills } from "@/lib/readme-docs";

export async function GET() {
  return new Response(readCanonicalSkills(), {
    headers: {
      "cache-control": "public, max-age=0, must-revalidate",
      "content-disposition": 'inline; filename="SKILLS.md"',
      "content-type": "text/markdown; charset=utf-8"
    }
  });
}
