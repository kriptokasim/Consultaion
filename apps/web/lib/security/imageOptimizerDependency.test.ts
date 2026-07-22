import { describe, expect, it } from "vitest";
import sharp from "sharp";

describe("image optimizer native dependency", () => {
  it("uses the patched Sharp runtime and can process an image", async () => {
    expect(sharp.versions.sharp).toBe("0.35.0");

    const source = Buffer.from(
      '<svg xmlns="http://www.w3.org/2000/svg" width="2" height="3"><rect width="2" height="3" fill="red"/></svg>',
    );
    const optimized = await sharp(source).png().toBuffer();
    const metadata = await sharp(optimized).metadata();

    expect(metadata.format).toBe("png");
    expect(metadata.width).toBe(2);
    expect(metadata.height).toBe(3);
  });
});
