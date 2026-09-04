"use client";

import { useRef, useState } from "react";
import type { PointerEvent } from "react";

const MODELS = [
  { label: "GPT", tone: "from-amber-300/90 to-amber-500/70" },
  { label: "G", tone: "from-slate-200 to-slate-400/80" },
  { label: "C", tone: "from-amber-200/90 to-amber-400/70" },
  { label: "Q", tone: "from-slate-200 to-slate-400/80" },
  { label: "A", tone: "from-amber-200/90 to-amber-400/70" },
  { label: "M", tone: "from-slate-200 to-slate-400/80" },
];

export function InteractiveParliamentChamber() {
  const dragRef = useRef({ x: 0, y: 0, baseX: 0, baseY: 0, active: false });
  const [rotation, setRotation] = useState({ x: -7, y: 0 });
  const [hovered, setHovered] = useState(false);

  const clamp = (value: number, min: number, max: number) =>
    Math.min(max, Math.max(min, value));

  const startDrag = (clientX: number, clientY: number) => {
    dragRef.current = {
      x: clientX,
      y: clientY,
      baseX: rotation.x,
      baseY: rotation.y,
      active: true,
    };
  };

  const moveDrag = (clientX: number, clientY: number) => {
    if (!dragRef.current.active) return;
    const dx = clientX - dragRef.current.x;
    const dy = clientY - dragRef.current.y;
    setRotation({
      x: clamp(dragRef.current.baseX - dy * 0.18, -20, 15),
      y: clamp(dragRef.current.baseY + dx * 0.22, -28, 28),
    });
  };

  const endDrag = () => {
    dragRef.current.active = false;
  };

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    startDrag(event.clientX, event.clientY);
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    moveDrag(event.clientX, event.clientY);
  };

  const handlePointerUp = (event: PointerEvent<HTMLDivElement>) => {
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Pointer capture can already be released by the browser.
    }
    endDrag();
  };

  return (
    <div
      className="relative aspect-[16/10] w-full select-none overflow-hidden rounded-[24px] border border-amber-200/50 bg-[radial-gradient(circle_at_50%_30%,rgba(255,248,224,0.95),rgba(236,233,226,0.95)_55%,rgba(218,213,204,0.98))] shadow-2xl shadow-amber-900/10 backdrop-blur dark:border-amber-700/30 dark:bg-[radial-gradient(circle_at_50%_25%,rgba(59,51,40,0.95),rgba(25,29,38,0.98)_62%,rgba(15,18,25,1))] dark:shadow-amber-900/20"
      aria-label="Interactive Parliament chamber. Drag to rotate the chamber view."
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={endDrag}
      onPointerLeave={() => {
        endDrag();
        setHovered(false);
      }}
      onPointerEnter={() => setHovered(true)}
      onDoubleClick={() => setRotation({ x: -7, y: 0 })}
      style={{ touchAction: "none", cursor: dragRef.current.active ? "grabbing" : "grab" }}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,rgba(255,255,255,0.55),transparent_34%),linear-gradient(to_bottom,transparent_58%,rgba(35,30,24,0.18))] dark:bg-[radial-gradient(circle_at_50%_18%,rgba(255,255,255,0.08),transparent_28%),linear-gradient(to_bottom,transparent_55%,rgba(0,0,0,0.36))]" />

      <div className="absolute inset-[8%]" style={{ perspective: "900px" }}>
        <div
          className="relative h-full w-full"
          style={{
            transformStyle: "preserve-3d",
            transform: `rotateX(${rotation.x}deg) rotateY(${rotation.y}deg)`,
            transition: dragRef.current.active ? "none" : "transform 160ms ease-out",
          }}
        >
          <div
            className="absolute left-[16%] top-[38%] h-[48%] w-[68%] rounded-[50%] border-[16px] border-b-0 border-amber-800/80 bg-gradient-to-b from-amber-700/90 to-amber-950/90 shadow-[0_22px_34px_rgba(70,45,15,0.24)] dark:border-amber-500/30 dark:from-amber-700/40 dark:to-amber-950/60"
            style={{ transform: "rotateX(68deg) translateZ(-20px)" }}
          />

          <div
            className="absolute left-[21%] top-[23%] h-[50%] w-[58%] rounded-[50%] border-[12px] border-slate-400/50 bg-slate-100/70 shadow-inner dark:border-slate-600/50 dark:bg-slate-900/55"
            style={{ transform: "rotateX(67deg) translateZ(4px)" }}
          />

          <div
            className="absolute left-[43%] top-[55%] h-[14%] w-[14%] rounded-[18px] border border-amber-300/70 bg-gradient-to-b from-amber-200 to-amber-500 shadow-xl shadow-amber-700/20 dark:border-amber-300/40 dark:from-amber-300/80 dark:to-amber-700/80"
            style={{ transform: "translateZ(68px)" }}
          >
            <div className="absolute inset-x-2 top-2 h-1 rounded-full bg-white/70" />
            <div className="absolute inset-x-4 bottom-3 h-2 rounded-full bg-amber-900/20" />
          </div>

          <div className="absolute left-[44%] top-[2%] h-[28%] w-[12%]" style={{ transform: "translateZ(34px)" }}>
            <div className="mx-auto h-3/4 w-2/3 rounded-[45%] border border-amber-200/70 bg-gradient-to-b from-amber-100 via-amber-300 to-amber-700 shadow-lg dark:from-amber-100/80 dark:via-amber-300/70 dark:to-amber-800/70" />
            <div className="mx-auto mt-[-4%] h-3 w-10 rounded-full bg-amber-700/60 dark:bg-amber-300/30" />
          </div>

          {MODELS.map((model, index) => {
            const angle = 205 + index * 26;
            const radiusX = 40;
            const radiusY = 30;
            const x = 50 + Math.cos((angle * Math.PI) / 180) * radiusX;
            const y = 58 + Math.sin((angle * Math.PI) / 180) * radiusY;
            return (
              <div
                key={`${model.label}-${index}`}
                className="absolute -translate-x-1/2 -translate-y-1/2"
                style={{ left: `${x}%`, top: `${y}%`, transform: "translateZ(55px)" }}
              >
                <div className={`flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br ${model.tone} text-[9px] font-bold text-slate-800 shadow-md ring-2 ring-white/50 dark:text-slate-900 dark:ring-slate-950/50`}>
                  {model.label}
                </div>
              </div>
            );
          })}

          <div
            className="absolute inset-x-[31%] top-[86%] h-1 rounded-full bg-amber-300/75 shadow-[0_0_20px_rgba(245,158,11,0.35)]"
            style={{ transform: "translateZ(90px)" }}
          />
        </div>
      </div>

      <div className="absolute left-4 top-4 rounded-full border border-white/40 bg-white/65 px-3 py-1 text-[10px] font-semibold tracking-wide text-slate-700 shadow-sm backdrop-blur dark:border-white/10 dark:bg-slate-950/45 dark:text-slate-200">
        Parliament chamber
      </div>
      <div className={`pointer-events-none absolute bottom-4 left-4 rounded-full border border-slate-200/80 bg-white/80 px-3 py-1 text-[10px] text-slate-600 shadow-sm backdrop-blur transition-opacity dark:border-slate-700/70 dark:bg-slate-950/65 dark:text-slate-300 ${hovered ? "opacity-100" : "opacity-85"}`}>
        Drag to rotate · double-click to reset
      </div>
    </div>
  );
}

export default InteractiveParliamentChamber;
