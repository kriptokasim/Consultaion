import type { Metadata } from "next"
import GalleryClient from "./GalleryClient"

export const metadata: Metadata = {
  title: "Gallery | Consultaion",
  description: "Explore curated examples of multi-model AI decision making.",
}

export default function GalleryPage() {
  return <GalleryClient />
}
