import { redirect } from "next/navigation";

/**
 * PS07: Models/Leaderboard/Hall of Fame consolidated onto /models
 * (ModelRegistrySurface), switched by hash instead of separate routes.
 * This route is kept, not deleted, so existing links/bookmarks still
 * resolve — it just forwards into the consolidated surface's hall-of-fame
 * tab. See app/(marketing)/models/page.tsx.
 */
export default function HallOfFameRedirect() {
  redirect("/models#hall-of-fame");
}
