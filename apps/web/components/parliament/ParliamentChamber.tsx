import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Bot } from "lucide-react";
import type { Member, Role } from "./types";

export interface ParliamentChamberProps {
  members: Member[];
  activeId?: string;
  speakerSeconds?: number;
  layout?: "hemicycle" | "benches";
}

const getRoleColor = (role: Role) => {
  const colors = {
    agent: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    critic: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    judge: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    synthesizer: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  };
  return colors[role] || colors.agent;
};

const getRoleDot = (role: Role, isActive: boolean) => {
  const colors = {
    agent: "bg-blue-500",
    critic: "bg-purple-500",
    judge: "bg-amber-500",
    synthesizer: "bg-emerald-500",
  };
  const baseColor = colors[role] || colors.agent;
  return `${baseColor} ${isActive ? "animate-pulse" : ""}`;
};

export default function ParliamentChamber({
  members,
  activeId,
  speakerSeconds,
  layout = "hemicycle",
}: ParliamentChamberProps) {
  return (
    <section 
      className="py-12 [--parl-blue:#0B1D3A] [--parl-gold:#D4AF37] [--muted:#101827]"
      aria-labelledby="chamber-title"
    >
      <div className="container mx-auto px-4">
        <div className="text-center mb-8">
          <h2 id="chamber-title" className="text-3xl md:text-4xl font-bold text-[--parl-gold] mb-2">
            The Chamber
          </h2>
          <p className="text-base text-white/70">AI Models in Active Deliberation</p>
        </div>

        <div className={`max-w-6xl mx-auto grid gap-4 ${
          layout === "hemicycle" 
            ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" 
            : "grid-cols-1 md:grid-cols-2"
        }`}>
          {members.map((member) => {
            const isActive = member.id === activeId;
            
            return (
              <Card
                key={member.id}
                className={`p-5 transition-all bg-[--muted] border-white/10 ${
                  isActive ? "border-2 border-[--parl-gold] shadow-xl shadow-[--parl-gold]/20" : "hover:border-white/20"
                }`}
                role="article"
                aria-label={`${member.name}, ${member.role}${isActive ? ", currently speaking" : ""}`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="relative">
                      <div className="w-12 h-12 rounded-full bg-[--parl-gold]/10 flex items-center justify-center">
                        <Bot className="w-6 h-6 text-[--parl-gold]" aria-hidden="true" />
                      </div>
                      <div 
                        className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-[--muted] ${getRoleDot(member.role, isActive)}`}
                        aria-hidden="true"
                      />
                    </div>
                    <div>
                      <h3 className="font-bold text-base text-white">{member.name}</h3>
                      {member.party && (
                        <p className="text-xs text-white/60">{member.party}</p>
                      )}
                    </div>
                  </div>
                  
                  {isActive && speakerSeconds !== undefined && (
                    <div 
                      className="flex items-center justify-center w-10 h-10 rounded-full bg-[--parl-gold]/20 border border-[--parl-gold]/40"
                      aria-label={`${speakerSeconds} seconds`}
                    >
                      <span className="text-xs font-bold text-[--parl-gold]">{speakerSeconds}s</span>
                    </div>
                  )}
                </div>

                <Badge className={`${getRoleColor(member.role)} border text-xs`}>
                  {member.role.charAt(0).toUpperCase() + member.role.slice(1)}
                </Badge>
              </Card>
            );
          })}
        </div>
      </div>
    </section>
  );
}
