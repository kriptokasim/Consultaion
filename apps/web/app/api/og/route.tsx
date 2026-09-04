import { ImageResponse } from "next/og";

export const runtime = "edge";

function clampTitle(value: string, max = 92) {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > max ? `${normalized.slice(0, max - 1)}…` : normalized;
}

function parsePercent(value: string | null) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.max(0, Math.min(100, Math.round(numeric)));
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const title = clampTitle(searchParams.get("title") || "Shared Arena Run");
    const modelsCount = Math.max(1, Number.parseInt(searchParams.get("models") || "4", 10) || 4);
    const divergence = parsePercent(searchParams.get("divergence"));
    const confidence = parsePercent(searchParams.get("confidence"));
    const winner = searchParams.get("winner") ? clampTitle(searchParams.get("winner")!, 36) : null;
    const verified = searchParams.get("verified") === "1";
    const signal = divergence !== null ? `${divergence}% model divergence` : "Multiple independent AI perspectives";

    return new ImageResponse(
      (
        <div style={{ height: "100%", width: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", background: "linear-gradient(135deg, #0f172a 0%, #111827 58%, #451a03 100%)", padding: "54px 64px", color: "white", fontFamily: "sans-serif" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ fontSize: "24px", fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase", color: "#fbbf24" }}>Consultaion</div>
              <div style={{ marginTop: "8px", fontSize: "17px", color: "#cbd5e1" }}>Where AI models agree — and disagree.</div>
            </div>
            {verified && <div style={{ display: "flex", alignItems: "center", border: "1px solid #34d399", background: "rgba(16,185,129,.12)", color: "#a7f3d0", borderRadius: "999px", padding: "10px 18px", fontSize: "18px", fontWeight: 800 }}>✓ VERIFIED</div>}
          </div>

          <div style={{ display: "flex", flexDirection: "column", maxWidth: "1040px" }}>
            <div style={{ fontSize: "50px", lineHeight: 1.14, fontWeight: 800, letterSpacing: "-0.02em" }}>{title}</div>
            <div style={{ display: "flex", alignItems: "center", gap: "18px", marginTop: "30px" }}>
              <div style={{ display: "flex", alignItems: "center", border: "1px solid rgba(251,191,36,.28)", background: "rgba(251,191,36,.10)", borderRadius: "16px", padding: "13px 20px", fontSize: "22px", fontWeight: 700, color: "#fde68a" }}>{signal}</div>
              <div style={{ display: "flex", alignItems: "center", border: "1px solid rgba(255,255,255,.10)", background: "rgba(255,255,255,.06)", borderRadius: "16px", padding: "13px 20px", fontSize: "22px", color: "#e2e8f0" }}>{modelsCount} models</div>
              {confidence !== null && <div style={{ display: "flex", alignItems: "center", border: "1px solid rgba(96,165,250,.25)", background: "rgba(96,165,250,.10)", borderRadius: "16px", padding: "13px 20px", fontSize: "22px", color: "#bfdbfe" }}>{confidence}% confidence</div>}
            </div>
            {winner && <div style={{ marginTop: "22px", display: "flex", fontSize: "20px", color: "#cbd5e1" }}>Leading verdict: <span style={{ marginLeft: "8px", color: "white", fontWeight: 800 }}>{winner}</span></div>}
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
            <div style={{ display: "flex", fontSize: "18px", color: "#94a3b8" }}>Independent perspectives · semantic divergence · decision synthesis</div>
            <div style={{ display: "flex", fontSize: "18px", fontWeight: 700, color: "#fbbf24" }}>consultaion.com</div>
          </div>
        </div>
      ),
      { width: 1200, height: 630 }
    );
  } catch {
    return new Response("Failed to generate the image", { status: 500 });
  }
}
