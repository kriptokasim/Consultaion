"use client";

import React, { useEffect } from "react";
import anime from "animejs";

interface VoteWaveProps {
  ids: string[];
  triggerKey: string;
}

export const VoteWave: React.FC<VoteWaveProps> = ({ ids, triggerKey }) => {
  useEffect(() => {
    if (!ids.length) return;

    const targets = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => !!el);

    if (!targets.length) return;

    anime({
      targets,
      translateY: [-6, 0],
      scale: [0.96, 1],
      opacity: [0.4, 1],
      duration: 450,
      delay: anime.stagger(80),
      easing: "easeOutQuad",
    });
  }, [ids, triggerKey]);

  return null;
};
