import { useEffect, useRef, useState } from "react";
import LiquidGlass from "liquid-glass-react";

const stillPointer = { x: 0, y: 0 };

export default function GlassSurface({ children, className = "", ...props }) {
  const container = useRef(null);
  const [reducedMotion, setReducedMotion] = useState(() =>
    window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return (
    <div {...props} ref={container} className={`liquid-surface ${className}`}>
      <LiquidGlass
        className="liquid-surface__body"
        displacementScale={48}
        blurAmount={0.08}
        saturation={115}
        aberrationIntensity={1}
        elasticity={reducedMotion ? 0 : 0.12}
        cornerRadius={2}
        padding="0"
        style={{ position: "relative", top: "0px", left: "50%", width: "100%" }}
        {...(reducedMotion
          // Fixed external coordinates also suppress the library's fallback mouse listener.
          ? { globalMousePos: stillPointer, mouseOffset: stillPointer }
          : { mouseContainer: container })}
      >
        {children}
      </LiquidGlass>
    </div>
  );
}
