import { ImageResponse } from "next/og"

export const size = {
  width: 64,
  height: 64,
}

export const contentType = "image/png"

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 16,
          backgroundColor: "#0F172A",
        }}
      >
        <svg width="44" height="44" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M6 4h14c9.389 0 17 7.611 17 17s-7.611 17-17 17H6V4Z"
            stroke="#FBBF24"
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
          <path d="M6 21h14c5 0 9 4 9 9" stroke="#FDE68A" strokeWidth="4" strokeLinecap="round" fill="none" />
        </svg>
      </div>
    ),
    { ...size },
  )
}
