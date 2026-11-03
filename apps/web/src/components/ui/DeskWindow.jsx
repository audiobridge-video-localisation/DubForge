import "./DeskWindow.css";

// DubForge's own window: a file-type chip instead of traffic lights.
export default function DeskWindow({ ext, title, className = "", children }) {
  return (
    <div className={`dw ${className}`}>
      <div className="dw-bar">
        <span className="dw-ext">{ext}</span>
        {title && <span className="dw-title">{title}</span>}
        <span className="dw-x" aria-hidden="true">
          ×
        </span>
      </div>
      <div className="dw-body">{children}</div>
    </div>
  );
}
