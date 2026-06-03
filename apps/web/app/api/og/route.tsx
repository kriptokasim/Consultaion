import { ImageResponse } from "next/og";

export const runtime = "edge";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const title = searchParams.get("title") || "Shared Arena Run";
    const modelsCount = searchParams.get("models") || "4";

    return new ImageResponse(
      (
        <div
          style={{
            height: "100%",
            width: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#0f172a", // slate-900
            padding: "40px",
            fontFamily: "sans-serif",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "30px",
            }}
          >
            <div
              style={{
                fontSize: "24px",
                fontWeight: "bold",
                color: "#60a5fa", // blue-400
                textTransform: "uppercase",
                letterSpacing: "0.1em",
              }}
            >
              Consultaion
            </div>
          </div>
          
          <div
            style={{
              display: "flex",
              fontSize: "64px",
              fontWeight: "bold",
              color: "white",
              textAlign: "center",
              lineHeight: 1.2,
              marginBottom: "40px",
              maxWidth: "800px",
            }}
          >
            {title}
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "20px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                fontSize: "32px",
                color: "#cbd5e1", // slate-300
                backgroundColor: "#1e293b", // slate-800
                padding: "16px 32px",
                borderRadius: "16px",
              }}
            >
              {modelsCount} AI models compared
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                fontSize: "32px",
                color: "#cbd5e1",
                backgroundColor: "#1e293b",
                padding: "16px 32px",
                borderRadius: "16px",
              }}
            >
              Synthesized final answer
            </div>
          </div>
        </div>
      ),
      {
        width: 1200,
        height: 630,
      }
    );
  } catch (e: any) {
    return new Response(`Failed to generate the image`, {
      status: 500,
    });
  }
}
