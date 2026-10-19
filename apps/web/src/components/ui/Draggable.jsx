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
}) {
  const el = useRef(null);
  const drag = useRef(null);

  const onDown = (e) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = {
      id: e.pointerId,
      sx: e.clientX,
      sy: e.clientY,
      ox: el.current.offsetLeft,
      oy: el.current.offsetTop,
    };
    el.current.classList.add("dragging");
    e.preventDefault();
  };
  const onMove = (e) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    el.current.style.left = `${d.ox + e.clientX - d.sx}px`;
    el.current.style.top = `${d.oy + e.clientY - d.sy}px`;
  };
  const onUp = (e) => {
    if (drag.current?.id !== e.pointerId) return;
    drag.current = null;
    el.current.classList.remove("dragging");
  };

  return (
    <div
      ref={el}
      className={`draggable ${className}`}
      style={{ left: x, top: y, transform: `rotate(${rot}deg)`, ...style }}
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onPointerCancel={onUp}
    >
      {children}
    </div>
  );
}
