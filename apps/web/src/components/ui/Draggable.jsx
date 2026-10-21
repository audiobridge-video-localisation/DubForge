import { useRef } from "react";
import "./Draggable.css";

// Absolutely-positioned element you can drag around. Position is written straight to
// the DOM during a drag so it never triggers React re-renders.
export default function Draggable({
  x,
  y,
  rot = 0,
  className = "",
  style,
  children,
  onPositionChange,
  onDrop,
  interactionProps,
}) {
  const el = useRef(null);
  const drag = useRef(null);

  const onDown = (e) => {
    if (e.button !== 0) return;
    if (e.target.closest("a, button, input, select, textarea")) return;
    const scale =
      el.current.parentElement.getBoundingClientRect().width /
      el.current.parentElement.offsetWidth;
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = {
      id: e.pointerId,
      sx: e.clientX,
      sy: e.clientY,
      ox: el.current.offsetLeft,
      oy: el.current.offsetTop,
      scale,
    };
    el.current.classList.add("dragging");
    e.preventDefault();
  };
  const onMove = (e) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    const x = d.ox + (e.clientX - d.sx) / d.scale;
    const y = d.oy + (e.clientY - d.sy) / d.scale;
    el.current.style.left = `${x}px`;
    el.current.style.top = `${y}px`;
    onPositionChange?.({ x, y }, el.current);
  };
  const onUp = (e) => {
    if (drag.current?.id !== e.pointerId) return;
    drag.current = null;
    el.current.classList.remove("dragging");
    onDrop?.(el.current);
  };

  return (
    <div
      ref={el}
      className={`draggable ${className}`}
      style={{
        left: x,
        top: y,
        transform: `rotate(${rot}deg)`,
        "--card-rotation": `${rot}deg`,
        ...style,
      }}
      {...interactionProps}
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onPointerCancel={onUp}
    >
      {children}
    </div>
  );
}
