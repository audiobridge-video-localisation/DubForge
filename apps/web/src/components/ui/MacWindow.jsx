import "./MacWindow.css";

export default function MacWindow({
  title,
  className = "",
  style,
  screenClass = "",
  children,
}) {
  return (
    <div className={`win ${className}`} style={style}>
      <div className="bar">
        <div className="dots">
          <b />
          <b />
          <b />
        </div>
        {title && <div className="t">{title}</div>}
      </div>
      <div className={`screen ${screenClass}`}>{children}</div>
    </div>
  );
}
