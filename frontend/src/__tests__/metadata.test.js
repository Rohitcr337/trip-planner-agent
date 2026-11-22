// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const html = readFileSync(fileURLToPath(new URL("../../index.html", import.meta.url)), "utf8");
const TITLE = "Cairn: trip plans traced to their sources";
const DESCRIPTION = "Itineraries built from travel guides, checked against your budget and travel times.";

describe("document metadata", () => {
  it("has the product title", () => {
    expect(html).toContain(`<title>${TITLE}</title>`);
  });

  it("has description and Open Graph tags", () => {
    expect(html).toContain(`<meta name="description" content="${DESCRIPTION}" />`);
    expect(html).toContain(`<meta property="og:title" content="${TITLE}" />`);
    expect(html).toContain(`<meta property="og:description" content="${DESCRIPTION}" />`);
  });

  it("uses an inline SVG favicon of the three-stone mark", () => {
    const icon = html.match(/<link rel="icon" type="image\/svg\+xml" href="data:image\/svg\+xml,([^"]+)"/);
    expect(icon).not.toBeNull();
    expect(decodeURIComponent(icon[1]).match(/<rect /g)).toHaveLength(3);
  });
});
